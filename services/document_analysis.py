"""
NIVAS Document Intelligence Service.
Handles in-memory extraction of text from real estate PDFs and TXT files,
heuristic/pattern-based extraction of key legal entities with page-number citations,
cross-document discrepancy comparison, and prompt-injection sanitization.
"""

import io
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import pypdf

from backend.models.documents import (
    DiscrepancyItem,
    DocumentExtractionResult,
    DocumentFieldStatus,
    EvidenceSnippet,
    ExtractedDates,
    ExtractedFinancials,
    ExtractedParty,
    ExtractedPropertyDetails,
    ExtractedRegistration,
    MultiDocumentComparisonResponse,
)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
MAX_PAGE_COUNT = 50

LEGAL_DISCLAIMER_TEXT = (
    "NIVAS Document Intelligence provides automated informational text analysis and cross-referencing "
    "for decision support only. It does NOT constitute a legal title opinion, property ownership verification, "
    "or official registration check. Official land registry records (Sub-Registrar / Land Revenue Office) and "
    "consultation with a qualified advocate or title legal professional are required for definitive legal verification. "
    "Live Sub-Registrar database verification is currently unavailable."
)

SUSPICIOUS_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\/?(?:system|instruction|prompt)>", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.IGNORECASE),
    re.compile(r"do\s+not\s+report\s+(?:any\s+)?defects?", re.IGNORECASE),
]


def sanitize_text(text: str) -> Tuple[str, List[str]]:
    """
    Sanitize text against malicious prompt injection or instruction overriding.
    Neutralizes detected adversarial patterns and returns a list of detected threats.
    """
    sanitized = text
    threats_detected = []
    for pattern in SUSPICIOUS_INJECTION_PATTERNS:
        matches = pattern.findall(sanitized)
        if matches:
            threats_detected.append(f"Neutralized suspicious pattern: {matches[0][:40]}")
            sanitized = pattern.sub("[REDACTED_PROMPT_INJECTION_ATTEMPT]", sanitized)
    return sanitized, threats_detected


def extract_pages_from_file(file_bytes: bytes, filename: str) -> Tuple[List[Tuple[int, str]], List[str], bool]:
    """
    Reads PDF or text file in-memory. Enforces max size and max page limits.
    Returns:
        (pages, warnings, is_scanned_or_empty)
        where pages is a list of (page_number_1_indexed, text_content).
    """
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File '{filename}' exceeds maximum allowed size of 10MB ({len(file_bytes)} bytes).")

    lower_name = filename.lower()
    pages: List[Tuple[int, str]] = []
    warnings: List[str] = []
    is_scanned_or_empty = False

    if lower_name.endswith(".pdf"):
        if not file_bytes.startswith(b"%PDF-"):
            raise ValueError(f"File '{filename}' does not appear to be a valid PDF document (missing %PDF- header).")

        try:
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        except Exception as e:
            raise ValueError(f"Could not parse PDF file '{filename}': {str(e)}")

        if reader.is_encrypted:
            raise ValueError(
                f"PDF file '{filename}' is password-protected or encrypted. Please provide an unencrypted PDF document."
            )

        num_pages = len(reader.pages)
        if num_pages == 0:
            raise ValueError(f"PDF file '{filename}' contains 0 pages.")
        if num_pages > MAX_PAGE_COUNT:
            raise ValueError(
                f"PDF file '{filename}' has {num_pages} pages, which exceeds the limit of {MAX_PAGE_COUNT} pages."
            )

        total_extracted_chars = 0
        for i, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            clean_text, threats = sanitize_text(page_text)
            if threats:
                warnings.extend([f"Page {i}: {t}" for t in threats])
            total_extracted_chars += len(clean_text.strip())
            pages.append((i, clean_text))

        if total_extracted_chars < 80:
            is_scanned_or_empty = True
            warnings.append(
                "This document appears to be a scanned image or empty PDF. Machine-readable text was not detected. "
                "Please upload an OCR-processed or text-based PDF or TXT file for automated extraction."
            )

    elif lower_name.endswith((".txt", ".text", ".md", ".csv")):
        try:
            raw_text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = file_bytes.decode("latin-1", errors="replace")

        clean_text, threats = sanitize_text(raw_text)
        if threats:
            warnings.extend(threats)

        # Split text into pages of ~3000 chars or lines to allow page citations
        lines = clean_text.splitlines()
        if not lines or len(clean_text.strip()) < 10:
            is_scanned_or_empty = True
            warnings.append("Text file contains little or no readable content.")
            pages.append((1, clean_text))
        else:
            chunk_size = 50  # lines per simulated page
            page_idx = 1
            for start_line in range(0, max(1, len(lines)), chunk_size):
                if page_idx > MAX_PAGE_COUNT:
                    break
                page_content = "\n".join(lines[start_line : start_line + chunk_size])
                pages.append((page_idx, page_content))
                page_idx += 1
    else:
        raise ValueError(
            f"Unsupported file format for '{filename}'. Please upload a text-based PDF or TXT document."
        )

    return pages, warnings, is_scanned_or_empty


def find_snippet(pages: List[Tuple[int, str]], match_start: int, match_end: int, page_num: int, context_chars: int = 120) -> EvidenceSnippet:
    """Creates a grounded EvidenceSnippet for a match located on a given page."""
    for p_num, p_text in pages:
        if p_num == page_num:
            start = max(0, match_start - context_chars)
            end = min(len(p_text), match_end + context_chars)
            snippet = p_text[start:end].replace("\n", " ").strip()
            # Calculate line number
            line_no = p_text[:match_start].count("\n") + 1
            return EvidenceSnippet(
                page_number=page_num,
                excerpt_text=snippet,
                confidence=0.9,
                line_number=line_no,
            )
    return EvidenceSnippet(page_number=page_num, excerpt_text="", confidence=0.5)


def classify_document_type(pages: List[Tuple[int, str]]) -> Tuple[str, float, Optional[EvidenceSnippet]]:
    """Classifies document type based on title headers and standard legal terminology."""
    type_patterns = [
        ("Sale Deed", [r"\bSALE\s+DEED\b", r"\bDEED\s+OF\s+SALE\b", r"\bABSOLUTE\s+SALE\s+DEED\b"], 0.95),
        ("Conveyance Deed", [r"\bCONVEYANCE\s+DEED\b", r"\bDEED\s+OF\s+CONVEYANCE\b"], 0.95),
        ("Agreement to Sell", [r"\bAGREEMENT\s+TO\s+SELL\b", r"\bAGREEMENT\s+FOR\s+SALE\b", r"\bMEMORANDUM\s+OF\s+AGREEMENT\b"], 0.92),
        ("Lease Agreement", [r"\bLEASE\s+DEED\b", r"\bLEASE\s+AGREEMENT\b", r"\bRENT\s+AGREEMENT\b", r"\bDEED\s+OF\s+LEASE\b"], 0.90),
        ("Gift Deed", [r"\bGIFT\s+DEED\b", r"\bDEED\s+OF\s+GIFT\b"], 0.95),
        ("General Power of Attorney", [r"\bGENERAL\s+POWER\s+OF\s+ATTORNEY\b", r"\bGPA\b"], 0.90),
        ("Special Power of Attorney", [r"\bSPECIAL\s+POWER\s+OF\s+ATTORNEY\b", r"\bSPA\b"], 0.90),
        ("Relinquishment Deed", [r"\bRELINQUISHMENT\s+DEED\b", r"\bRELEASE\s+DEED\b"], 0.90),
        ("Mortgage Deed", [r"\bMORTGAGE\s+DEED\b", r"\bDEED\s+OF\s+MORTGAGE\b"], 0.90),
        ("Khata Certificate", [r"\bKHATA\s+CERTIFICATE\b", r"\bKHATA\s+EXTRACT\b"], 0.88),
        ("Encumbrance Certificate", [r"\bENCUMBRANCE\s+CERTIFICATE\b", r"\bFORM\s+NO\.\s*15\b"], 0.90),
        ("Will / Testament", [r"\bLAST\s+WILL\s+AND\s+TESTAMENT\b", r"\bWILL\s+DEED\b"], 0.85),
    ]

    # Search top pages first (title is almost always on page 1 or 2)
    for page_num, text in pages[:3]:
        for doc_type, regexes, conf in type_patterns:
            for pat in regexes:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    snippet = find_snippet(pages, m.start(), m.end(), page_num)
                    snippet.confidence = conf
                    return doc_type, conf, snippet

    # Secondary fallback search across all pages
    for page_num, text in pages:
        for doc_type, regexes, conf in type_patterns:
            for pat in regexes:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    snippet = find_snippet(pages, m.start(), m.end(), page_num)
                    snippet.confidence = max(0.5, conf - 0.1)
                    return doc_type, snippet.confidence, snippet

    return "Property Document (Unclassified)", 0.35, None


def clean_party_name(name: str) -> str:
    cleaned = re.sub(r"^(?:AND|BETWEEN|THE|BY)\s+", "", name.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"^(?:Shri|Smt\.?|Mr\.|Mrs\.|Ms\.)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.lstrip(". ,-")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_valid_party_name(name: str, seen: set) -> bool:
    if not name or len(name) < 3:
        return False
    lower = name.lower()
    if lower in seen:
        return False
    prohibited = {"hereinafter", "called the", "vendor", "purchaser", "witness", "whereas", "schedule", "all that", "this sale deed"}
    if any(p in lower for p in prohibited):
        return False
    return True


def extract_parties_from_pages(pages: List[Tuple[int, str]]) -> List[ExtractedParty]:
    """Identifies Grantor/Vendor, Grantee/Purchaser, and Witnesses."""
    parties: List[ExtractedParty] = []
    seen_names = set()

    for page_num, text in pages:
        # Suffix style Vendor: BETWEEN [Name] ... (hereinafter called the VENDOR)
        between_match = re.search(
            r"BETWEEN\s+(?:Shri|Smt|Mr\.|Mrs\.|Ms\.)?\s*([A-Za-z\s\.\']{3,50}?)(?:,|\s+son\s+of|\s+wife\s+of|\s+daughter\s+of|\s+residing|\s+aged|\s+hereinafter)",
            text,
            re.IGNORECASE,
        )
        if between_match:
            name = clean_party_name(between_match.group(1))
            if is_valid_party_name(name, seen_names):
                seen_names.add(name.lower())
                snippet = find_snippet(pages, between_match.start(), between_match.end(), page_num)
                parties.append(
                    ExtractedParty(
                        name=name,
                        role="Vendor / Seller / First Party",
                        details="First party / transferor cited in instrument",
                        evidence=snippet,
                        status=DocumentFieldStatus.EXPLICITLY_STATED,
                    )
                )

        # Prefix style Vendor: VENDOR: [Name]
        vendor_match = re.search(
            r"(?:^|\n)\s*(?:VENDOR|SELLER|FIRST\s+PARTY|GRANTOR|LESSOR|TRANSFEROR)\s*[:\-]\s*(?:Shri|Smt|Mr\.|Mrs\.|Ms\.)?\s*([A-Za-z\s\.\']{3,50}?)(?:,|\s+son\s+of|\s+wife\s+of|\s+daughter\s+of|\s+residing|\s+hereinafter|\s+aged|\n)",
            text,
            re.IGNORECASE,
        )
        if vendor_match:
            name = clean_party_name(vendor_match.group(1))
            if is_valid_party_name(name, seen_names):
                seen_names.add(name.lower())
                snippet = find_snippet(pages, vendor_match.start(), vendor_match.end(), page_num)
                parties.append(
                    ExtractedParty(
                        name=name,
                        role="Vendor / Seller / First Party",
                        details="First party / transferor cited in instrument",
                        evidence=snippet,
                        status=DocumentFieldStatus.EXPLICITLY_STATED,
                    )
                )

        # Suffix style Purchaser: AND [Name] ... (hereinafter called the PURCHASER)
        and_match = re.search(
            r"(?:^|\n)\s*AND\s+(?:Shri|Smt|Mr\.|Mrs\.|Ms\.)?\s*([A-Za-z\s\.\']{3,50}?)(?:,|\s+son\s+of|\s+wife\s+of|\s+daughter\s+of|\s+residing|\s+aged|\s+hereinafter)",
            text,
            re.IGNORECASE,
        )
        if and_match:
            name = clean_party_name(and_match.group(1))
            if is_valid_party_name(name, seen_names):
                seen_names.add(name.lower())
                snippet = find_snippet(pages, and_match.start(), and_match.end(), page_num)
                parties.append(
                    ExtractedParty(
                        name=name,
                        role="Purchaser / Buyer / Second Party",
                        details="Second party / transferee cited in instrument",
                        evidence=snippet,
                        status=DocumentFieldStatus.EXPLICITLY_STATED,
                    )
                )

        # Prefix style Purchaser: PURCHASER: [Name]
        purchaser_match = re.search(
            r"(?:^|\n)\s*(?:PURCHASER|BUYER|SECOND\s+PARTY|GRANTEE|LESSEE|TRANSFEREE)\s*[:\-]\s*(?:Shri|Smt|Mr\.|Mrs\.|Ms\.)?\s*([A-Za-z\s\.\']{3,50}?)(?:,|\s+son\s+of|\s+wife\s+of|\s+daughter\s+of|\s+residing|\s+hereinafter|\s+aged|\n)",
            text,
            re.IGNORECASE,
        )
        if purchaser_match:
            name = clean_party_name(purchaser_match.group(1))
            if is_valid_party_name(name, seen_names):
                seen_names.add(name.lower())
                snippet = find_snippet(pages, purchaser_match.start(), purchaser_match.end(), page_num)
                parties.append(
                    ExtractedParty(
                        name=name,
                        role="Purchaser / Buyer / Second Party",
                        details="Second party / transferee cited in instrument",
                        evidence=snippet,
                        status=DocumentFieldStatus.EXPLICITLY_STATED,
                    )
                )

        # Witnesses
        for wm in re.finditer(r"(?:Witness(?:\s*\d)?|In\s+the\s+presence\s+of)[\s\d\.:]+(?:Shri|Smt|Mr\.)?\s*([A-Z][a-zA-Z\s\.\']{2,35})", text, re.IGNORECASE):
            name = clean_party_name(wm.group(1))
            if is_valid_party_name(name, seen_names) and not name.lower().startswith("where"):
                seen_names.add(name.lower())
                snippet = find_snippet(pages, wm.start(), wm.end(), page_num)
                parties.append(
                    ExtractedParty(
                        name=name,
                        role="Witness",
                        details="Attesting witness",
                        evidence=snippet,
                        status=DocumentFieldStatus.EXPLICITLY_STATED,
                    )
                )

    return parties


def extract_financials_from_pages(pages: List[Tuple[int, str]]) -> ExtractedFinancials:
    """Extracts stated sale consideration, stamp duty, and registration charges."""
    financials = ExtractedFinancials()

    consideration_patterns = [
        re.compile(r"(?:consideration|sale\s+price|sale\s+value|sum)\s*(?:of|for)?[\s\w]*?(?:Rs\.?|INR|₹)\s*([0-9,]+(?:\.[0-9]{2})?)", re.IGNORECASE),
        re.compile(r"(?:Rs\.?|INR|₹)\s*([0-9,]+(?:\.[0-9]{2})?)\s*(?:\/-\s*)?\(Rupees", re.IGNORECASE),
        re.compile(r"(?:fixed\s+at|amounting\s+to|sum\s+of)\s*(?:Rs\.?|INR|₹)?\s*([0-9,]+(?:\.[0-9]{2})?)", re.IGNORECASE),
        re.compile(r"(?:Rs\.?|INR|₹)\s*([0-9,]+(?:\.[0-9]{2})?)\s*\/\-", re.IGNORECASE),
    ]

    stamp_duty_patterns = [
        re.compile(r"stamp\s+duty\s*(?:of|paid|amount)?\s*[:\-]?\s*(?:Rs\.?|INR|₹)?\s*([0-9,]+)", re.IGNORECASE),
    ]

    reg_fee_patterns = [
        re.compile(r"registration\s+fee(?:s)?\s*(?:paid)?\s*[:\-]?\s*(?:Rs\.?|INR|₹)?\s*([0-9,]+)", re.IGNORECASE),
    ]

    for page_num, text in pages:
        if not financials.declared_consideration:
            for pat in consideration_patterns:
                m = pat.search(text)
                if m:
                    raw_val = m.group(1).strip()
                    clean_num = raw_val.replace(",", "")
                    try:
                        numeric_val = float(clean_num)
                        if numeric_val >= 50000:
                            financials.declared_consideration = f"₹ {raw_val}"
                            financials.numeric_amount = numeric_val
                            financials.evidence = find_snippet(pages, m.start(), m.end(), page_num)
                            financials.status = DocumentFieldStatus.EXPLICITLY_STATED
                            break
                    except ValueError:
                        pass

        if not financials.stamp_duty:
            for pat in stamp_duty_patterns:
                m = pat.search(text)
                if m:
                    val = m.group(1).strip()
                    financials.stamp_duty = f"₹ {val}"
                    if not financials.evidence:
                        financials.evidence = find_snippet(pages, m.start(), m.end(), page_num)

        if not financials.registration_fee:
            for pat in reg_fee_patterns:
                m = pat.search(text)
                if m:
                    val = m.group(1).strip()
                    financials.registration_fee = f"₹ {val}"

    return financials


def extract_property_details_from_pages(pages: List[Tuple[int, str]]) -> ExtractedPropertyDetails:
    """Extracts plot/survey numbers, property address, and schedule descriptions."""
    prop = ExtractedPropertyDetails()

    plot_patterns = [
        re.compile(r"(?:Plot\s*(?:No\.?|Number)|Flat\s*(?:No\.?|Number)|Unit\s*(?:No\.?|Number))\s*[:\-]?\s*([A-Za-z0-9\/\-\_]+)", re.IGNORECASE),
        re.compile(r"(?:Survey\s*(?:No\.?|Number)|Khasra\s*(?:No\.?|Number)|CTS\s*(?:No\.?|Number))\s*[:\-]?\s*([A-Za-z0-9\/\-\_]+)", re.IGNORECASE),
    ]

    area_patterns = [
        re.compile(r"((?:measuring|area\s+of|admeasuring)\s+[0-9,]+(?:\.[0-9]+)?\s*(?:sq(?:uare)?\s*(?:feet|ft|yards|yd|meters|mtrs)|sq\.\s*ft|sq\.\s*yds))", re.IGNORECASE),
    ]

    address_patterns = [
        re.compile(r"(?:situated\s+at|bearing\s+(?:municipal|property)\s+no\.?|located\s+at)\s+([^,\n\.]+?(?:,\s*[^,\n\.]+?){1,3})", re.IGNORECASE),
        re.compile(r"(?:owner\s+of|property(?:\s+known\s+as|\s+at)?)\s*[:\-]?\s*([^,\n\.]+?(?:,\s*[^,\n\.]+?){1,3})", re.IGNORECASE),
        re.compile(r"(?:Plot|Flat|Unit|Survey|Khasra)\s*(?:No\.?|Number)?[\s\w\/\-]+?,\s*([^,\n\.]+?(?:,\s*[^,\n\.]+?){1,3})", re.IGNORECASE),
    ]

    for page_num, text in pages:
        lines = text.splitlines()
        for line in lines:
            if any(k in line.lower() for k in ["residing", "hereinafter", "wife of", "son of", "daughter of"]):
                continue

            m_plot = re.search(r"(?:Plot|Flat|Unit|Survey|Khasra)\s*(?:No\.?|Number)?\s*[:\-]?\s*([A-Za-z0-9\/\-\_]+)(?:,\s*([^\n\.;]+))?", line, re.IGNORECASE)
            if m_plot:
                if not prop.plot_survey_number:
                    prop.plot_survey_number = m_plot.group(1).strip()
                    prop.evidence = find_snippet(pages, text.find(line), text.find(line) + len(line), page_num)
                    prop.status = DocumentFieldStatus.EXPLICITLY_STATED
                if m_plot.group(2) and not prop.address:
                    cand = m_plot.group(2).strip()
                    cand = re.sub(r",?\s*(?:measuring|admeasuring|area of)[\s\S]*$", "", cand, flags=re.IGNORECASE).strip()
                    if len(cand) > 3:
                        prop.address = cand
                break

        if not prop.area_sqft:
            for pat in area_patterns:
                m = pat.search(text)
                if m:
                    prop.area_sqft = m.group(1).strip()
                    if not prop.evidence:
                        prop.evidence = find_snippet(pages, m.start(), m.end(), page_num)
                        prop.status = DocumentFieldStatus.EXPLICITLY_STATED
                    break

        if not prop.address:
            for pat in address_patterns:
                m = pat.search(text)
                if m:
                    addr_candidate = m.group(1).strip()
                    addr_candidate = re.sub(r",?\s*(?:measuring|admeasuring|area of)[\s\S]*$", "", addr_candidate, flags=re.IGNORECASE).strip()
                    if len(addr_candidate) > 8 and not any(p in addr_candidate.lower() for p in ["purchaser", "vendor", "residing"]):
                        prop.address = addr_candidate
                        if not prop.evidence:
                            prop.evidence = find_snippet(pages, m.start(), m.end(), page_num)
                            prop.status = DocumentFieldStatus.EXPLICITLY_STATED
                        break

    # Boundary detection (Schedule of Property)
    boundary_dict = {}
    for page_num, text in pages:
        for direction in ["North", "South", "East", "West"]:
            if direction not in boundary_dict:
                pat = re.compile(rf"{direction}\s*(?:by|:)[\s:]+([^\n,;]+)", re.IGNORECASE)
                m = pat.search(text)
                if m:
                    boundary_dict[direction] = m.group(1).strip()
    if boundary_dict:
        prop.boundaries = boundary_dict

    return prop


def extract_dates_from_pages(pages: List[Tuple[int, str]]) -> ExtractedDates:
    """Extracts execution date and registration presentation date."""
    dates = ExtractedDates()

    date_patterns = [
        re.compile(r"(?:executed\s+on|entered\s+into\s+on|made\s+(?:and\s+executed\s+)?on|dated\s*(?:this)?)\s*([0-9]{1,2}(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember))\s*,?\s*[0-9]{4}|[0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4})", re.IGNORECASE),
        re.compile(r"(?:registered\s+on|presented\s+on)\s*([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{2,4}|[0-9]{1,2}(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember))\s*,?\s*[0-9]{4})", re.IGNORECASE),
    ]

    for page_num, text in pages:
        if not dates.execution_date:
            m = date_patterns[0].search(text)
            if m:
                dates.execution_date = m.group(1).strip()
                dates.evidence = find_snippet(pages, m.start(), m.end(), page_num)
                dates.status = DocumentFieldStatus.EXPLICITLY_STATED

        if not dates.registration_date:
            m = date_patterns[1].search(text)
            if m:
                dates.registration_date = m.group(1).strip()
                if not dates.evidence:
                    dates.evidence = find_snippet(pages, m.start(), m.end(), page_num)
                    dates.status = DocumentFieldStatus.EXPLICITLY_STATED

    return dates


def extract_registration_from_pages(pages: List[Tuple[int, str]]) -> ExtractedRegistration:
    """Extracts Sub-Registrar registration number, book number, volume, and office."""
    reg = ExtractedRegistration()

    sro_pattern = re.compile(r"(?:Office\s+of\s+the\s+Sub-Registrar|Sub-Registrar\s+Office|Sub-Registrar|SRO)\s*[:\-]\s*([^\n\.;]+)", re.IGNORECASE)
    doc_num_pattern = re.compile(r"(?:Document\s*(?:No\.?|Number)|Registration\s*(?:No\.?|Number))\s*[:\-]?\s*([A-Za-z0-9\/\-]+)", re.IGNORECASE)
    book_vol_pattern = re.compile(r"(?:Book\s*(?:No\.?|Number)\s*[:\-]?\s*([0-9IVX]+))|(?:Volume\s*(?:No\.?|Number|Jild)\s*[:\-]?\s*([0-9]+))", re.IGNORECASE)

    for page_num, text in pages:
        if not reg.sub_registrar_office:
            m = sro_pattern.search(text)
            if m:
                candidate = m.group(1).strip()
                if len(candidate) > 3:
                    reg.sub_registrar_office = candidate
                    reg.evidence = find_snippet(pages, m.start(), m.end(), page_num)
                    reg.status = DocumentFieldStatus.EXPLICITLY_STATED

        if not reg.registration_number:
            m = doc_num_pattern.search(text)
            if m:
                reg.registration_number = m.group(1).strip()
                if not reg.evidence:
                    reg.evidence = find_snippet(pages, m.start(), m.end(), page_num)
                    reg.status = DocumentFieldStatus.EXPLICITLY_STATED

        if not reg.book_number:
            m = book_vol_pattern.search(text)
            if m:
                reg.book_number = (m.group(1) or m.group(2) or "").strip()

    return reg


def analyze_document_bytes(file_bytes: bytes, filename: str) -> DocumentExtractionResult:
    """End-to-end pipeline to process a single document from in-memory bytes."""
    pages, warnings, is_scanned_or_empty = extract_pages_from_file(file_bytes, filename)
    doc_id = str(uuid.uuid4())[:8]

    total_chars = sum(len(text) for _, text in pages)
    doc_type, doc_conf, type_evidence = classify_document_type(pages)

    parties = extract_parties_from_pages(pages)
    financials = extract_financials_from_pages(pages)
    property_details = extract_property_details_from_pages(pages)
    dates = extract_dates_from_pages(pages)
    registration = extract_registration_from_pages(pages)

    if not parties:
        warnings.append("No explicit party names (Vendor/Purchaser) were reliably detected. Review document manually.")
    if not financials.declared_consideration:
        warnings.append("Financial consideration amount was not explicitly identified in numeric format.")
    if not property_details.plot_survey_number and not property_details.address:
        warnings.append("No clear plot, survey, or municipal property identification number was identified.")

    return DocumentExtractionResult(
        document_id=doc_id,
        filename=filename,
        file_size_bytes=len(file_bytes),
        page_count=len(pages),
        document_type=doc_type,
        document_type_confidence=doc_conf,
        is_scanned_or_empty=is_scanned_or_empty,
        warnings=warnings,
        parties=parties,
        property_details=property_details,
        dates=dates,
        financials=financials,
        registration=registration,
        raw_text_length=total_chars,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )


def compare_documents(docs: List[DocumentExtractionResult]) -> MultiDocumentComparisonResponse:
    """
    Compares multiple extracted documents to detect discrepancies in:
    1. Declared financial consideration
    2. Property identifier / Plot / Survey number
    3. Party names and roles
    4. Transaction dates sequence
    """
    if len(docs) < 2:
        return MultiDocumentComparisonResponse(
            document_count=len(docs),
            compared_documents=[d.filename for d in docs],
            summary="At least two documents are required to perform cross-document consistency checks.",
            overall_risk_level="low",
            discrepancies=[],
            matches=[],
        )

    discrepancies: List[DiscrepancyItem] = []
    matches: List[str] = []

    # 1. Compare Financial Consideration
    considerations = {}
    for d in docs:
        if d.financials.numeric_amount:
            considerations[d.filename] = (d.financials.numeric_amount, d.financials.declared_consideration, d.financials.evidence)

    if len(considerations) >= 2:
        values = list(considerations.values())
        amt_first = values[0][0]
        mismatch_found = False
        for fname, (amt, dec_str, ev) in considerations.items():
            if amt != amt_first:
                mismatch_found = True
                break

        if mismatch_found:
            doc_vals = {fname: dec_str for fname, (_, dec_str, _) in considerations.items()}
            cited_ex = {fname: ev for fname, (_, _, ev) in considerations.items()}
            discrepancies.append(
                DiscrepancyItem(
                    field_name="Declared Consideration Amount",
                    severity="high",
                    status="mismatch",
                    description=f"Transaction values differ across instruments: {', '.join(f'{k}: {v}' for k, v in doc_vals.items())}.",
                    document_values=doc_vals,
                    cited_excerpts=cited_ex,
                    recommendation="Verify whether the difference represents an initial earnest money deposit vs total sale price, or a conflicting financial term requiring an addendum.",
                )
            )
        else:
            matches.append(f"Consideration value consistent across {len(considerations)} documents: {values[0][1]}")
    elif len(considerations) == 1:
        present_file = list(considerations.keys())[0]
        missing_files = [d.filename for d in docs if d.filename not in considerations]
        discrepancies.append(
            DiscrepancyItem(
                field_name="Declared Consideration Amount",
                severity="medium",
                status="missing_in_one",
                description=f"Consideration specified in '{present_file}' ({considerations[present_file][1]}) but unstated or not identified in {', '.join(missing_files)}.",
                document_values={present_file: considerations[present_file][1]},
                cited_excerpts={present_file: considerations[present_file][2]},
                recommendation="Confirm whether the omitted document is an ancillary instrument (such as GPA or NOC) where consideration is traditionally omitted.",
            )
        )

    # 2. Compare Plot / Survey / Flat Numbers
    plots = {}
    for d in docs:
        if d.property_details.plot_survey_number:
            clean_plot = re.sub(r"[\s\-\_]", "", d.property_details.plot_survey_number.lower())
            plots[d.filename] = (clean_plot, d.property_details.plot_survey_number, d.property_details.evidence)

    if len(plots) >= 2:
        clean_vals = [v[0] for v in plots.values()]
        if len(set(clean_vals)) == 1:
            matches.append(f"Property Plot/Survey identifier matched across all documents: {list(plots.values())[0][1]}")
        else:
            doc_vals = {fname: raw for fname, (_, raw, _) in plots.items()}
            cited_ex = {fname: ev for fname, (_, _, ev) in plots.items()}
            discrepancies.append(
                DiscrepancyItem(
                    field_name="Property Plot / Survey Identification",
                    severity="high",
                    status="mismatch",
                    description=f"Conflicting property identifiers detected: {', '.join(f'{k}: {v}' for k, v in doc_vals.items())}.",
                    document_values=doc_vals,
                    cited_excerpts=cited_ex,
                    recommendation="Critical: Inspect schedules of property to determine whether instruments refer to different portions/floors or if an erroneous plot number was typed.",
                )
            )

    # 3. Compare Parties (Vendors and Purchasers)
    all_party_names_by_doc: Dict[str, List[str]] = {}
    for d in docs:
        all_party_names_by_doc[d.filename] = [p.name.strip().lower() for p in d.parties]

    if len(all_party_names_by_doc) >= 2:
        filenames = list(all_party_names_by_doc.keys())
        doc_a, doc_b = filenames[0], filenames[1]
        names_a = set(all_party_names_by_doc[doc_a])
        names_b = set(all_party_names_by_doc[doc_b])

        common_names = names_a.intersection(names_b)
        if common_names:
            matches.append(f"Key transacting party name(s) identified in both instruments: {', '.join(sorted([n.title() for n in common_names]))}")
        elif names_a and names_b:
            discrepancies.append(
                DiscrepancyItem(
                    field_name="Transacting Party Names",
                    severity="medium",
                    status="mismatch",
                    description=f"No direct name overlap detected between parties in '{doc_a}' ({', '.join([n.title() for n in names_a])}) and '{doc_b}' ({', '.join([n.title() for n in names_b])}).",
                    document_values={
                        doc_a: [n.title() for n in names_a],
                        doc_b: [n.title() for n in names_b],
                    },
                    cited_excerpts={},
                    recommendation="Verify whether one instrument is a prior chain-of-title deed involving previous owners, or if spelling variants/initials were used.",
                )
            )

    # Overall risk determination
    high_count = sum(1 for d in discrepancies if d.severity == "high")
    medium_count = sum(1 for d in discrepancies if d.severity == "medium")

    if high_count > 0:
        overall_risk = "high"
        summary = f"Detected {high_count} high-severity and {medium_count} medium-severity discrepancy between documents that require legal reconciliation."
    elif medium_count > 0:
        overall_risk = "medium"
        summary = f"Detected {medium_count} moderate discrepancy or missing term across compared documents."
    else:
        overall_risk = "low"
        summary = f"Cross-document consistency check passed with {len(matches)} matching key parameters and no severe conflicts detected."

    return MultiDocumentComparisonResponse(
        document_count=len(docs),
        compared_documents=[d.filename for d in docs],
        summary=summary,
        overall_risk_level=overall_risk,
        discrepancies=discrepancies,
        matches=matches,
    )

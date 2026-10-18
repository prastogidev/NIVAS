"""
Data models for NIVAS Document Intelligence.
Defines schemas for extracted real estate document entities, page-level evidence citations,
and cross-document discrepancy detection.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentFieldStatus(str, Enum):
    EXPLICITLY_STATED = "explicitly_stated"
    INFERRED = "inferred"
    MISSING = "missing"
    CONFLICTING = "conflicting"


class EvidenceSnippet(BaseModel):
    page_number: int = Field(..., description="1-indexed document page number where evidence was found")
    excerpt_text: str = Field(..., description="Exact context excerpt extracted from the document")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for the extraction")
    line_number: Optional[int] = Field(None, description="Approximate line number within the page")


class ExtractedParty(BaseModel):
    name: str = Field(..., description="Name of the party (individual, corporate, or representative)")
    role: str = Field(..., description="Role in transaction (e.g. Vendor/Seller, Purchaser/Buyer, Witness, Mortgagor)")
    details: Optional[str] = Field(None, description="Associated details such as parentage, address, PAN or Aadhaar")
    evidence: Optional[EvidenceSnippet] = None
    status: DocumentFieldStatus = DocumentFieldStatus.EXPLICITLY_STATED


class ExtractedFinancials(BaseModel):
    declared_consideration: Optional[str] = Field(None, description="Stated transaction consideration in text")
    numeric_amount: Optional[float] = Field(None, description="Parsed numeric amount in INR")
    currency: str = Field("INR", description="Currency of consideration")
    stamp_duty: Optional[str] = Field(None, description="Reported stamp duty paid")
    registration_fee: Optional[str] = Field(None, description="Reported registration fees paid")
    evidence: Optional[EvidenceSnippet] = None
    status: DocumentFieldStatus = DocumentFieldStatus.MISSING


class ExtractedRegistration(BaseModel):
    registration_number: Optional[str] = Field(None, description="Document or registration entry number")
    book_number: Optional[str] = Field(None, description="Book number in Sub-Registrar records")
    volume_number: Optional[str] = Field(None, description="Volume / Jild number")
    page_range: Optional[str] = Field(None, description="Registration page numbers / folio")
    sub_registrar_office: Optional[str] = Field(None, description="Sub-Registrar Office (SRO) name and jurisdiction")
    registration_date: Optional[str] = Field(None, description="Date of formal registration")
    evidence: Optional[EvidenceSnippet] = None
    status: DocumentFieldStatus = DocumentFieldStatus.MISSING


class ExtractedPropertyDetails(BaseModel):
    address: Optional[str] = Field(None, description="Full or partial property address/description")
    plot_survey_number: Optional[str] = Field(None, description="Survey, Khasra, Plot, or Flat number")
    khasra_number: Optional[str] = Field(None, description="Specific Khasra or Khatoni number if mentioned")
    area_sqft: Optional[str] = Field(None, description="Area in sq ft, sq yards, or sq meters")
    boundaries: Optional[Dict[str, str]] = Field(None, description="Boundaries (North, South, East, West)")
    evidence: Optional[EvidenceSnippet] = None
    status: DocumentFieldStatus = DocumentFieldStatus.MISSING


class ExtractedDates(BaseModel):
    execution_date: Optional[str] = Field(None, description="Date agreement or deed was signed / executed")
    registration_date: Optional[str] = Field(None, description="Date presented or registered with authority")
    evidence: Optional[EvidenceSnippet] = None
    status: DocumentFieldStatus = DocumentFieldStatus.MISSING


class DocumentExtractionResult(BaseModel):
    document_id: str
    filename: str
    file_size_bytes: int
    page_count: int
    document_type: str = Field(..., description="Classified type, e.g. Sale Deed, Conveyance, Agreement to Sell, Lease")
    document_type_confidence: float = Field(0.0, ge=0.0, le=1.0)
    is_scanned_or_empty: bool = Field(False, description="True if no digital text stream was detected")
    warnings: List[str] = Field(default_factory=list)
    parties: List[ExtractedParty] = Field(default_factory=list)
    property_details: ExtractedPropertyDetails
    dates: ExtractedDates
    financials: ExtractedFinancials
    registration: ExtractedRegistration
    raw_text_length: int
    analyzed_at: str


class DiscrepancyItem(BaseModel):
    field_name: str
    severity: str = Field("medium", description="high, medium, low, info")
    status: str = Field("mismatch", description="match, mismatch, missing_in_one, partial_match")
    description: str
    document_values: Dict[str, Any]
    cited_excerpts: Dict[str, Optional[EvidenceSnippet]] = Field(default_factory=dict)
    recommendation: str


class MultiDocumentComparisonResponse(BaseModel):
    document_count: int
    compared_documents: List[str]
    summary: str
    overall_risk_level: str = Field("low", description="low, medium, high")
    discrepancies: List[DiscrepancyItem] = Field(default_factory=list)
    matches: List[str] = Field(default_factory=list)


class DocumentAnalysisResponse(BaseModel):
    documents: List[DocumentExtractionResult]
    comparison: Optional[MultiDocumentComparisonResponse] = None
    legal_disclaimer: str
    registry_verification_status: str = "not_verified_live_registry_unavailable"

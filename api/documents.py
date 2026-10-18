"""
FastAPI Router for NIVAS Document Intelligence.
Endpoints for uploading and analyzing real estate documents (PDF/TXT),
extracting grounded metadata with page citations, and detecting cross-document discrepancies.
"""

import logging
from typing import List
from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.models.documents import (
    DocumentAnalysisResponse,
    DocumentExtractionResult,
    MultiDocumentComparisonResponse,
)
from backend.services.document_analysis import (
    LEGAL_DISCLAIMER_TEXT,
    analyze_document_bytes,
    compare_documents,
)

logger = logging.getLogger("nivas.api.documents")

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/analyze", response_model=DocumentAnalysisResponse)
async def analyze_documents(
    files: List[UploadFile] = File(..., description="PDF or TXT property documents (max 10MB each, max 50 pages)")
):
    """
    Upload one or more real estate documents (PDF or TXT).
    Extracts structured legal entities (parties, property schedule, consideration, dates, registration)
    grounded with page citations, sanitizes against prompt injection, and executes cross-document
    consistency checks if multiple files are submitted.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one document file (PDF or TXT) must be uploaded.",
        )

    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A maximum of 10 documents can be processed simultaneously.",
        )

    extracted_results: List[DocumentExtractionResult] = []

    for file in files:
        filename = file.filename or "uploaded_document"
        try:
            content_bytes = await file.read()
            if not content_bytes:
                raise ValueError(f"Uploaded file '{filename}' is empty.")

            result = analyze_document_bytes(content_bytes, filename)
            extracted_results.append(result)
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(ve),
            )
        except Exception as e:
            logger.exception(f"Error processing file '{filename}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"An error occurred while parsing '{filename}': {str(e)}",
            )

    comparison_result = None
    if len(extracted_results) >= 2:
        comparison_result = compare_documents(extracted_results)

    return DocumentAnalysisResponse(
        documents=extracted_results,
        comparison=comparison_result,
        legal_disclaimer=LEGAL_DISCLAIMER_TEXT,
        registry_verification_status="not_verified_live_registry_unavailable",
    )


@router.post("/compare", response_model=MultiDocumentComparisonResponse)
async def compare_extracted_documents(docs: List[DocumentExtractionResult]):
    """
    Compare previously extracted document schemas to evaluate consistency and flag discrepancies.
    """
    if len(docs) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least two extracted documents are required for comparative reconciliation.",
        )
    return compare_documents(docs)


@router.get("/sample-documents")
async def get_sample_document_data():
    """
    Provides pre-baked synthetic sample document contents (Agreement to Sell vs Sale Deed)
    so users can immediately evaluate the Document Intelligence workspace without uploading private files.
    """
    agreement_sample = (
        "AGREEMENT TO SELL\n"
        "This Agreement to Sell is made and entered into on this 14th day of March, 2024 at New Delhi.\n\n"
        "BETWEEN\n"
        "Shri Rajesh Kumar Sharma, son of Late Shri Mohan Lal Sharma, residing at B-42, Hauz Khas, New Delhi - 110016\n"
        "(hereinafter called the VENDOR / FIRST PARTY)\n\n"
        "AND\n"
        "Smt. Priya Anand Verma, wife of Shri Amit Verma, residing at D-12, Greater Kailash-I, New Delhi - 110048\n"
        "(hereinafter called the PURCHASER / SECOND PARTY)\n\n"
        "WHEREAS the Vendor is the absolute and undisputed owner of residential property situated at:\n"
        "Plot No. 104, Block-C, Defence Colony, New Delhi - 110024, measuring an area of 250 sq yards.\n\n"
        "NOW THIS AGREEMENT WITNESSETH AS UNDER:\n"
        "1. That the total agreed sale price of the said property has been fixed at Rs. 4,50,00,000/- (Rupees Four Crores Fifty Lakhs only).\n"
        "2. That the Purchaser has paid an earnest advance sum of Rs. 45,00,000/- via bank transfer.\n"
        "3. That the final Sale Deed shall be executed within 90 days upon payment of the remaining balance.\n\n"
        "IN WITNESS WHEREOF the parties have set their hands:\n"
        "Witness 1: Shri Vikram Malhotra\n"
        "Witness 2: Shri Sunil Saxena"
    )

    sale_deed_sample = (
        "ABSOLUTE SALE DEED\n"
        "This Sale Deed is executed on this 12th day of June, 2024 at New Delhi.\n\n"
        "BY AND BETWEEN\n"
        "Shri Rajesh Kumar Sharma, son of Late Shri Mohan Lal Sharma, residing at B-42, Hauz Khas, New Delhi - 110016\n"
        "(hereinafter called the VENDOR)\n\n"
        "AND\n"
        "Smt. Priya Anand Verma, wife of Shri Amit Verma, residing at D-12, Greater Kailash-I, New Delhi - 110048\n"
        "(hereinafter called the PURCHASER)\n\n"
        "SCHEDULE OF PROPERTY:\n"
        "All that residential piece and parcel of land known as Plot No. 104, Block-C, Defence Colony, New Delhi - 110024,\n"
        "measuring an area of 250 sq yards, bounded as:\n"
        "North by: Road 30ft wide\n"
        "South by: Plot No. 105\n"
        "East by: Plot No. 98\n"
        "West by: Service lane\n\n"
        "CONSIDERATION AND COVENANTS:\n"
        "That in consideration of sum of Rs. 4,50,00,000/- (Rupees Four Crores Fifty Lakhs only) fully received by the Vendor,\n"
        "the Vendor hereby transfers and conveys absolute title to the Purchaser.\n"
        "Stamp duty paid: Rs. 27,00,000/-. Registration fees paid: Rs. 4,50,000/-.\n"
        "Registered at Sub-Registrar Office: SRO-VII, Defence Colony, New Delhi.\n"
        "Document Number: DL-SR7-2024-8841, Book Number: 1, Volume Number: 1042.\n\n"
        "IN WITNESS WHEREOF the parties have affixed their signatures:\n"
        "Witness 1: Shri Vikram Malhotra\n"
        "Witness 2: Shri Sunil Saxena"
    )

    mismatched_sample = (
        "AGREEMENT TO SELL (AMENDED DRAFT)\n"
        "This Agreement to Sell is made on this 20th day of March, 2024.\n"
        "VENDOR: Shri Rajesh Kumar Sharma\n"
        "PURCHASER: Smt. Priya Anand Verma\n"
        "Property: Plot No. 104-A, Block-C, Defence Colony, New Delhi\n"
        "Total consideration of Rs. 4,80,00,000/- (Rupees Four Crores Eighty Lakhs only).\n"
        "Witness: Shri Vikram Malhotra"
    )

    return {
        "samples": [
            {
                "id": "agreement_sample",
                "filename": "Agreement_to_Sell_Defence_Colony.txt",
                "content": agreement_sample,
                "label": "Sample 1: Agreement to Sell",
            },
            {
                "id": "sale_deed_sample",
                "filename": "Sale_Deed_Defence_Colony.txt",
                "content": sale_deed_sample,
                "label": "Sample 2: Absolute Sale Deed (Consistent)",
            },
            {
                "id": "mismatched_sample",
                "filename": "Draft_Agreement_Conflict.txt",
                "content": mismatched_sample,
                "label": "Sample 3: Conflicting Draft (Price & Plot Conflict)",
            },
        ]
    }

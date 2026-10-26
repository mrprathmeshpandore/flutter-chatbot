from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import PDFDocument, User, ProgressLog
from app.schemas import PDFDocumentOut, PDFDocumentDetail, PDFPageOut
from app.services.auth_service import get_current_user
from app.services.pdf_service import process_and_save_pdf, delete_pdf_document

router = APIRouter(prefix="/pdf", tags=["PDF Library"])


@router.post(
    "/upload",
    response_model=PDFDocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a PDF textbook/document",
)
async def upload_pdf(
    file: UploadFile = File(..., description="PDF file to upload"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Uploads a PDF file, validates format and size limit, extracts text page-by-page,
    and indexes it for the AI Teacher.
    """
    content = await file.read()
    pdf_doc = process_and_save_pdf(file=file, content=content, user=current_user, db=db)

    # Log activity in progress
    log = ProgressLog(
        user_id=current_user.id,
        activity_type="pdf_uploaded",
        subject=pdf_doc.title,
        metadata_json={"pdf_id": pdf_doc.id, "page_count": pdf_doc.page_count},
    )
    db.add(log)
    db.commit()

    return pdf_doc


@router.get(
    "/",
    response_model=List[PDFDocumentOut],
    summary="List all uploaded PDFs for the current student",
)
def list_pdfs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns a list of all PDF documents owned by the authenticated student.
    """
    return (
        db.query(PDFDocument)
        .filter(PDFDocument.owner_id == current_user.id)
        .order_by(PDFDocument.uploaded_at.desc())
        .all()
    )


@router.get(
    "/{pdf_id}",
    response_model=PDFDocumentDetail,
    summary="Get details of a specific PDF",
)
def get_pdf(
    pdf_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the metadata, page count, and status of a specific PDF document.
    """
    pdf = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF with ID {pdf_id} not found.",
        )

    # Enforce ownership check
    if pdf.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this PDF document.",
        )

    return PDFDocumentDetail(
        id=pdf.id,
        title=pdf.title,
        filename=pdf.filename,
        file_size=pdf.file_size,
        page_count=pdf.page_count,
        uploaded_at=pdf.uploaded_at,
        owner_id=pdf.owner_id,
        pages=[PDFPageOut.model_validate(p) for p in pdf.pages],
        has_learning_path=(pdf.learning_path is not None),
    )


@router.delete(
    "/{pdf_id}",
    summary="Delete a PDF and all associated data",
)
def delete_pdf(
    pdf_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes a PDF document, extracted pages, and stored file from disk.
    """
    pdf = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF with ID {pdf_id} not found.",
        )

    # Enforce ownership check
    if pdf.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this PDF document.",
        )

    title = pdf.title
    delete_pdf_document(pdf, db)
    return {"detail": f"Document '{title}' successfully deleted.", "pdf_id": pdf_id}

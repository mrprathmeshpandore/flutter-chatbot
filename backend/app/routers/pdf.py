
import logging
import os
from typing import List
from app.tasks.quiz_tasks import generate_pdf_quiz_task

logger = logging.getLogger(__name__)
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PDFDocument, User, ProgressLog
from app.schemas import (
    PDFDocumentOut,
    PDFDocumentDetail,
    PDFPageOut,
)
from app.services.auth_service import get_current_user
from app.services.ai_service import AIService
from app.services.pdf_service import (
    process_and_save_pdf,
    delete_pdf_document,
)


router = APIRouter(prefix="/pdf", tags=["PDF Library"])


# --------------------------------------------------
# 1. Upload PDF
# --------------------------------------------------
@router.post(
    "/upload",
    response_model=PDFDocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and process a PDF textbook/document",
)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()

    pdf_doc = process_and_save_pdf(
        file=file,
        content=content,
        user=current_user,
        db=db,
    )

    background_tasks.add_task(
        generate_pdf_quiz_task,
        user_id=current_user.id,
        pdf_id=pdf_doc.id,
    )

    log = ProgressLog(
        user_id=current_user.id,
        pdf_id=pdf_doc.id,
        activity_type="pdf_uploaded",
        subject=pdf_doc.title,
        metadata_json={
            "pdf_id": pdf_doc.id,
            "page_count": pdf_doc.page_count,
        },
    )

    db.add(log)
    db.commit()

    return pdf_doc


# --------------------------------------------------
# 2. List all PDFs for logged-in user
# --------------------------------------------------
@router.get(
    "/",
    response_model=List[PDFDocumentOut],
    summary="List all uploaded PDFs",
)
def list_pdfs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(PDFDocument)
        .filter(PDFDocument.owner_id == current_user.id)
        .order_by(PDFDocument.uploaded_at.desc())
        .all()
    )


# --------------------------------------------------
# 3. Get PDF details
# --------------------------------------------------
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
    pdf = (
        db.query(PDFDocument)
        .filter(PDFDocument.id == pdf_id)
        .first()
    )

    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF with ID {pdf_id} not found.",
        )

    if pdf.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this PDF.",
        )

    return PDFDocumentDetail(
        id=pdf.id,
        title=pdf.title,
        filename=pdf.filename,
        file_size=pdf.file_size,
        page_count=pdf.page_count,
        uploaded_at=pdf.uploaded_at,
        owner_id=pdf.owner_id,
        pages=[
            PDFPageOut.model_validate(page)
            for page in pdf.pages
        ],
        has_learning_path=(pdf.learning_path is not None),
    )


# --------------------------------------------------
# 4. Open original PDF file
# --------------------------------------------------
@router.get(
    "/{pdf_id}/file",
    summary="Open or download the original PDF file",
)
def get_pdf_file(
    pdf_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pdf = (
        db.query(PDFDocument)
        .filter(PDFDocument.id == pdf_id)
        .first()
    )

    logger.debug("Requested PDF ID: %s, found: %s", pdf_id, pdf is not None)

    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF document not found.",
        )

    logger.debug("PDF Title: %s, Database Path: %r", pdf.title, pdf.file_path)

    absolute_path = (
        os.path.abspath(pdf.file_path)
        if pdf.file_path
        else None
    )

    file_exists = (
        os.path.isfile(absolute_path)
        if absolute_path
        else False
    )

    logger.debug("Absolute path: %s, exists: %s", absolute_path, file_exists)

    if pdf.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this PDF.",
        )

    if not file_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found on server.",
        )

    return FileResponse(
        path=absolute_path,
        media_type="application/pdf",
        filename=os.path.basename(pdf.filename),
        content_disposition_type="inline",
    )


# --------------------------------------------------
# 5. Delete PDF
# --------------------------------------------------
@router.delete(
    "/{pdf_id}",
    summary="Delete a PDF and its associated data",
)
def delete_pdf(
    pdf_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pdf = (
        db.query(PDFDocument)
        .filter(PDFDocument.id == pdf_id)
        .first()
    )

    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF with ID {pdf_id} not found.",
        )

    if pdf.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this PDF.",
        )

    title = pdf.title

    AIService.invalidate_pdf_cache(pdf_id)
    delete_pdf_document(pdf, db)

    return {
        "detail": f"Document '{title}' successfully deleted.",
        "pdf_id": pdf_id,
    }

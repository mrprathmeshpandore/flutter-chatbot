import os
import re
import uuid
from typing import List, Tuple, Dict, Any, Optional
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from pypdf import PdfReader
from app.config import settings
from app.models import PDFDocument, PDFPage, User


def validate_pdf_file(file: UploadFile, content: bytes) -> None:
    """
    Validates uploaded file format, magic bytes, and size limit.
    """
    # 1. Filename extension check
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF files (.pdf) are allowed.",
        )

    # 2. Size limit check
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB} MB.",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # 3. Magic header check (%PDF-)
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not appear to be a valid PDF document.",
        )


def process_and_save_pdf(
    file: UploadFile,
    content: bytes,
    user: User,
    db: Session,
) -> PDFDocument:
    """
    Saves the PDF to the uploads directory, extracts text page-by-page using pypdf,
    and creates PDFDocument and PDFPage records in the database.
    """
    validate_pdf_file(file, content)

    # Generate safe unique filename
    original_filename = os.path.basename(file.filename or "document.pdf")
    clean_base = re.sub(r"[^\w\-.]", "_", original_filename)
    unique_filename = f"{uuid.uuid4().hex[:10]}_{clean_base}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

    # Write file to disk
    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text using pypdf
    try:
        reader = PdfReader(file_path)
        page_count = len(reader.pages)
        if page_count == 0:
            raise ValueError("The PDF document contains no pages.")

        # Determine title (from metadata if available, else original filename)
        doc_title = original_filename.rsplit(".", 1)[0].replace("_", " ").title()
        if reader.metadata and reader.metadata.title:
            extracted_title = str(reader.metadata.title).strip()
            if extracted_title:
                doc_title = extracted_title

        # Create PDF document record
        pdf_doc = PDFDocument(
            owner_id=user.id,
            title=doc_title,
            filename=original_filename,
            file_path=file_path,
            file_size=len(content),
            page_count=page_count,
        )
        db.add(pdf_doc)
        db.flush()  # Populates pdf_doc.id

        # Extract each page
        for idx, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            # Clean non-printable characters and excessive blank lines
            cleaned_text = re.sub(r"\n{3,}", "\n\n", page_text.strip())
            
            pdf_page = PDFPage(
                pdf_id=pdf_doc.id,
                page_number=idx,
                text_content=cleaned_text,
            )
            db.add(pdf_page)

        db.commit()
        db.refresh(pdf_doc)
        return pdf_doc

    except Exception as e:
        db.rollback()
        # Clean up saved file if DB commit or extraction failed
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse PDF document: {str(e)}",
        )


def search_relevant_pages(
    pdf_id: int,
    query: str,
    db: Session,
    max_pages: int = 4,
) -> List[Dict[str, Any]]:
    """
    Searches pages in the specified PDF for query keywords and ranks them.
    Returns a list of dicts with {page_number, text_snippet, score}.
    """
    pages = db.query(PDFPage).filter(PDFPage.pdf_id == pdf_id).order_by(PDFPage.page_number).all()
    if not pages:
        return []

    # Clean query into keywords
    keywords = [re.escape(w.lower()) for w in re.findall(r"\w+", query) if len(w) > 2]
    
    scored_pages = []
    for page in pages:
        text_lower = page.text_content.lower()
        score = 0
        if not keywords:
            # If no significant keywords, match everything equally
            score = 1
        else:
            for kw in keywords:
                # Count keyword occurrences
                matches = len(re.findall(r"\b" + kw + r"\b", text_lower))
                score += matches * 2
                if kw in text_lower:
                    score += 1

        if score > 0 or len(pages) <= max_pages:
            scored_pages.append({
                "page_number": page.page_number,
                "text": page.text_content,
                "score": score,
            })

    # Sort descending by score
    scored_pages.sort(key=lambda x: x["score"], reverse=True)
    return scored_pages[:max_pages]


def delete_pdf_document(pdf: PDFDocument, db: Session) -> None:
    """
    Deletes the PDF from the database and removes its file from disk.
    """
    file_path = pdf.file_path
    db.delete(pdf)
    db.commit()

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

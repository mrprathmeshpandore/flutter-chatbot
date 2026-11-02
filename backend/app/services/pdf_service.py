import logging
import math
import os
import re
import uuid
from typing import List, Tuple, Dict, Any, Optional
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from pypdf import PdfReader
from app.config import settings
from app.models import PDFDocument, PDFPage, User

logger = logging.getLogger(__name__)


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
        status_413 = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        raise HTTPException(
            status_code=status_413,
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
    validates extractable text content, and creates PDFDocument and PDFPage records in the database.
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

        # Extract each page and normalize text
        total_extracted_chars = 0
        extracted_pages: List[Tuple[int, str]] = []
        for idx, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            # Reconnect hyphenated line-breaks: "represen-\ntation" -> "representation"
            cleaned_text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", page_text)
            # Clean excessive blank lines and leading/trailing whitespace
            cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text.strip())
            total_extracted_chars += len(cleaned_text)
            extracted_pages.append((idx, cleaned_text))

        # Check for empty or image-only scanned PDFs with no selectable text
        if total_extracted_chars == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded PDF contains no extractable text. Please ensure the document contains selectable text and is not an image-only scan.",
            )

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

        # Save pages
        for idx, cleaned_text in extracted_pages:
            pdf_page = PDFPage(
                pdf_id=pdf_doc.id,
                page_number=idx,
                text_content=cleaned_text,
            )
            db.add(pdf_page)

        db.commit()
        db.refresh(pdf_doc)

        logger.info(
            "PDF Processed | pdf_id=%s, owner_id=%s, filename='%s', pages=%d, total_chars=%d",
            pdf_doc.id,
            user.id,
            original_filename,
            page_count,
            total_extracted_chars,
        )
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


_STOP_WORDS = {
    "the", "and", "that", "have", "for", "not", "with", "you", "this", "but",
    "his", "from", "they", "say", "her", "she", "will", "one", "all", "would",
    "there", "their", "what", "about", "which", "when", "make", "can", "like",
    "time", "just", "him", "know", "take", "person", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then", "now",
    "look", "only", "come", "its", "over", "think", "also", "back", "after",
    "use", "two", "how", "our", "work", "first", "well", "way", "even", "new",
    "want", "because", "any", "these", "give", "day", "most", "us", "tell",
    "explain", "describe", "please", "does", "did", "are", "were", "been",
}


def chunk_page_text(
    page_number: int,
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> List[Dict[str, Any]]:
    """
    Splits page text into overlapping semantic windows while preserving sentence
    and paragraph boundaries, and tracking source page numbers for accurate citations.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    if len(clean_text) <= chunk_size:
        return [{
            "chunk_id": f"{page_number}_1",
            "page_number": page_number,
            "text": clean_text,
            "char_count": len(clean_text),
        }]

    chunks: List[Dict[str, Any]] = []
    start = 0
    text_len = len(clean_text)
    chunk_idx = 1

    while start < text_len:
        end = start + chunk_size
        if end >= text_len:
            chunk = clean_text[start:].strip()
            if chunk:
                chunks.append({
                    "chunk_id": f"{page_number}_{chunk_idx}",
                    "page_number": page_number,
                    "text": chunk,
                    "char_count": len(chunk),
                })
            break

        # Look for natural sentence or paragraph boundary near end of window
        split_idx = -1
        para_idx = clean_text.rfind("\n\n", start + chunk_overlap, end)
        if para_idx != -1:
            split_idx = para_idx + 2
        else:
            match = re.search(r"[\.\!\?]\s+", clean_text[start + chunk_overlap:end])
            if match:
                split_idx = start + chunk_overlap + match.end()
            else:
                space_idx = clean_text.rfind(" ", start + chunk_overlap, end)
                if space_idx != -1:
                    split_idx = space_idx + 1

        if split_idx == -1 or split_idx <= start:
            split_idx = end

        chunk = clean_text[start:split_idx].strip()
        if chunk:
            chunks.append({
                "chunk_id": f"{page_number}_{chunk_idx}",
                "page_number": page_number,
                "text": chunk,
                "char_count": len(chunk),
            })
            chunk_idx += 1

        # Advance start with overlap
        start = max(start + 1, split_idx - chunk_overlap)

    return chunks


def search_relevant_chunks(
    pdf_id: int,
    query: str,
    db: Session,
    max_chunks: Optional[int] = None,
    min_similarity: Optional[float] = None,
    user_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Retrieves the most relevant text chunks from a user's PDF document using
    BM25/TF-IDF token scoring, phrase matching, and confidence thresholding.
    Ensures PDF ID filtering and strict user isolation.
    """
    target_max_chunks = max_chunks or getattr(settings, "RAG_MAX_CHUNKS", 5)
    target_min_sim = (
        min_similarity
        if min_similarity is not None
        else getattr(settings, "RAG_MIN_SIMILARITY", 0.15)
    )
    chunk_size = getattr(settings, "RAG_CHUNK_SIZE", 800)
    chunk_overlap = getattr(settings, "RAG_CHUNK_OVERLAP", 150)

    # 1. User isolation check if user_id is provided
    if user_id is not None:
        doc = (
            db.query(PDFDocument)
            .filter(PDFDocument.id == pdf_id, PDFDocument.owner_id == user_id)
            .first()
        )
        if not doc:
            logger.warning(
                "RAG Access Denied | user_id=%s unauthorized for pdf_id=%s",
                user_id,
                pdf_id,
            )
            return [], 0.0

    # 2. Query all pages for the target PDF
    pages = (
        db.query(PDFPage.page_number, PDFPage.text_content)
        .filter(PDFPage.pdf_id == pdf_id)
        .order_by(PDFPage.page_number)
        .all()
    )
    if not pages:
        logger.info("RAG Search | pdf_id=%s has 0 pages in database", pdf_id)
        return [], 0.0

    # 3. Create semantic chunks across all pages
    all_chunks: List[Dict[str, Any]] = []
    for page_number, text_content in pages:
        page_chunks = chunk_page_text(
            page_number=page_number,
            text=text_content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        all_chunks.extend(page_chunks)

    if not all_chunks:
        return [], 0.0

    clean_q = query.strip().lower()

    # 4. Check for high-level document summary / overview intent
    is_overview = bool(
        re.search(
            r"\b(summar(y|ize)|overview|about|main\s+(topics?|concepts?|points?|ideas?)|what\s+is\s+this(\s+document|\s+pdf)?|key\s+takeaways?)\b",
            clean_q,
        )
    )
    if is_overview:
        # Opening chunks represent title, abstract, introduction, and high-level structure
        top_chunks = all_chunks[:target_max_chunks]
        for c in top_chunks:
            c["score"] = 0.90
        logger.info(
            "RAG Search | pdf_id=%s, overview_detected=True, returned=%d chunks, score=0.90",
            pdf_id,
            len(top_chunks),
        )
        return top_chunks, 0.90

    # 5. Tokenize query and remove stop-words
    raw_tokens = [w.lower() for w in re.findall(r"\b[A-Za-z0-9_-]{2,}\b", clean_q)]
    filtered_tokens = [w for w in raw_tokens if w not in _STOP_WORDS]
    keywords = filtered_tokens if filtered_tokens else raw_tokens

    if not keywords:
        return [], 0.0

    # 6. Compute document frequencies for smooth IDF across chunks
    total_chunks = len(all_chunks)
    df: Dict[str, int] = {}
    for kw in set(keywords):
        df[kw] = sum(1 for c in all_chunks if kw in c["text"].lower())

    scored_chunks: List[Dict[str, Any]] = []
    for chunk in all_chunks:
        text_lower = chunk["text"].lower()

        # Exact phrase match bonus
        phrase_bonus = 0.0
        if len(keywords) >= 2 and " ".join(keywords) in text_lower:
            phrase_bonus = 0.40
        elif clean_q in text_lower:
            phrase_bonus = 0.50

        # Token matching with IDF saturation
        token_score = 0.0
        matched_terms = 0
        for kw in set(keywords):
            cnt = text_lower.count(kw)
            if cnt > 0:
                matched_terms += 1
                n_docs = df.get(kw, 1)
                idf = math.log(1.0 + (total_chunks - n_docs + 0.5) / (n_docs + 0.5))
                tf = min(cnt, 4) / (min(cnt, 4) + 1.2)
                token_score += tf * max(idf, 0.25)

        match_ratio = matched_terms / len(set(keywords))
        combined_score = (token_score * 0.45) + (match_ratio * 0.35) + phrase_bonus
        normalized_score = min(1.0, combined_score)

        if normalized_score > 0.0:
            c_copy = dict(chunk)
            c_copy["score"] = round(normalized_score, 4)
            scored_chunks.append(c_copy)

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    max_score = scored_chunks[0]["score"] if scored_chunks else 0.0

    # 7. Apply similarity threshold
    passing_chunks = [c for c in scored_chunks if c["score"] >= target_min_sim]

    logger.info(
        "RAG Search | pdf_id=%s, query='%s', total_chunks=%d, passing_chunks=%d, max_score=%.3f, threshold=%.3f",
        pdf_id,
        clean_q[:50],
        total_chunks,
        len(passing_chunks),
        max_score,
        target_min_sim,
    )

    if not passing_chunks:
        return [], max_score

    selected = passing_chunks[:target_max_chunks]
    selected.sort(key=lambda x: (x["page_number"], x["chunk_id"]))
    return selected, max_score


def search_relevant_pages(
    pdf_id: int,
    query: str,
    db: Session,
    max_pages: int = 4,
    min_similarity: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Page-level compatibility search that aggregates high-scoring semantic chunks
    by page number while respecting relevance thresholds.
    """
    chunks, _ = search_relevant_chunks(
        pdf_id=pdf_id,
        query=query,
        db=db,
        max_chunks=max_pages * 2,
        min_similarity=min_similarity,
    )
    if not chunks:
        return []

    page_map: Dict[int, Dict[str, Any]] = {}
    for c in chunks:
        p_num = c["page_number"]
        if p_num not in page_map:
            page_map[p_num] = {
                "page_number": p_num,
                "text": c["text"],
                "score": c["score"],
            }
        else:
            page_map[p_num]["text"] += "\n\n" + c["text"]
            page_map[p_num]["score"] = max(page_map[p_num]["score"], c["score"])

    pages = list(page_map.values())
    pages.sort(key=lambda x: x["score"], reverse=True)
    return pages[:max_pages]



def delete_pdf_document(pdf: PDFDocument, db: Session) -> None:
    """
    Deletes a PDF, its related database records,
    and the original file from disk in a transaction-safe manner.
    """
    file_path = os.path.abspath(pdf.file_path) if pdf.file_path else None

    try:
        # Delete PDF and related database records.
        # DB-level ON DELETE CASCADE and SQLAlchemy ORM cascade
        # will remove all child records: pages, learning path, quizzes,
        # quiz questions, submissions, topic explanations, and progress logs.
        db.delete(pdf)
        db.commit()

    except Exception:
        db.rollback()
        import logging
        logging.exception("Failed to delete PDF document ID %s from database", getattr(pdf, 'id', None))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not delete PDF and its related data.",
        )

    # Remove original PDF file from storage ONLY after successful database commit
    if file_path and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except OSError:
            import logging
            logging.warning(
                "PDF database record deleted, but disk file cleanup failed: %s",
                file_path,
            )

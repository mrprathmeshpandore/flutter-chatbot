import json
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import PDFDocument, ProgressLog, User
from app.schemas import AskAIRequest, AskAIResponse
from app.services.auth_service import get_current_user
from app.services.ai_service import AIService, AIServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI Teacher"])


@router.post(
    "/ask",
    response_model=AskAIResponse,
    summary="Ask a question to the Personal AI Teacher",
)
def ask_ai(
    request: AskAIRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Answers a student question. When a PDF ID is provided:
    - Grounds the answer strictly in the PDF's extracted pages.
    - Cites exact source pages (e.g., [Page X]).
    - Never invents citations or claims facts were in the PDF if they were not.
    """
    pdf = None
    if request.pdf_id:
        pdf = db.query(PDFDocument).filter(PDFDocument.id == request.pdf_id).first()
        if not pdf:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PDF with ID {request.pdf_id} not found.",
            )
        if pdf.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this PDF document.",
            )

    history_dicts = [h.model_dump() for h in request.history] if request.history else None
    try:
        result = AIService.ask_ai_teacher(
            question=request.question,
            pdf=pdf,
            db=db,
            history=history_dicts,
            user_name=current_user.full_name,
            user_id=current_user.id,
        )
    except AIServiceError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        )

    # Log progress activity
    subject_title = pdf.title if pdf else "General AI Tutoring"
    log = ProgressLog(
        user_id=current_user.id,
        pdf_id=pdf.id if pdf else None,
        activity_type="ai_question",
        subject=subject_title,
        metadata_json={
            "used_pdf": result["used_pdf"],
            "source_pages": result["source_pages"],
            "pdf_id": pdf.id if pdf else None,
        },
    )
    db.add(log)
    db.commit()

    return AskAIResponse(
        answer=result["answer"],
        source_pages=result["source_pages"],
        used_pdf=result["used_pdf"],
        pdf_id=result["pdf_id"],
    )


@router.post(
    "/ask-stream",
    summary="Ask a question and stream the response in real time via Server-Sent Events",
)
def ask_ai_stream(
    request: AskAIRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Real-time streaming AI Teacher response using Server-Sent Events (SSE).
    Yields JSON events for metadata, incremental tokens, and completion for minimum TTFT.
    """
    pdf = None
    if request.pdf_id:
        pdf = db.query(PDFDocument).filter(PDFDocument.id == request.pdf_id).first()
        if not pdf:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PDF with ID {request.pdf_id} not found.",
            )
        if pdf.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this PDF document.",
            )

    history_dicts = [h.model_dump() for h in request.history] if request.history else None
    user_id = current_user.id
    user_name = current_user.full_name
    pdf_id = pdf.id if pdf else None
    subject_title = pdf.title if pdf else "General AI Tutoring"

    def sse_event_stream():
        try:
            stream_gen = AIService.ask_ai_teacher_stream(
                question=request.question,
                pdf=pdf,
                db=db,
                history=history_dicts,
                user_name=user_name,
                user_id=user_id,
            )
            for event in stream_gen:
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done":
                    # Record progress log upon successful completion
                    try:
                        log = ProgressLog(
                            user_id=user_id,
                            pdf_id=pdf_id,
                            activity_type="ai_question",
                            subject=subject_title,
                            metadata_json={
                                "used_pdf": event.get("used_pdf", False),
                                "source_pages": event.get("source_pages", []),
                                "pdf_id": pdf_id,
                            },
                        )
                        db.add(log)
                        db.commit()
                    except Exception as log_err:
                        logger.warning(f"Failed to record progress log for streaming question: {log_err}")
                        db.rollback()
        except AIServiceError as e:
            err_event = {"type": "error", "status_code": e.status_code, "detail": e.message}
            yield f"data: {json.dumps(err_event)}\n\n"
        except Exception as e:
            err_event = {"type": "error", "status_code": 500, "detail": str(e)}
            yield f"data: {json.dumps(err_event)}\n\n"

    from fastapi.responses import StreamingResponse
    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


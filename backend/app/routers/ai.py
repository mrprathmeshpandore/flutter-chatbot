from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import PDFDocument, ProgressLog, User
from app.schemas import AskAIRequest, AskAIResponse
from app.services.auth_service import get_current_user
from app.services.ai_service import AIService, AIServiceError

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
        activity_type="ai_question",
        subject=subject_title,
        metadata_json={
            "used_pdf": result["used_pdf"],
            "source_pages": result["source_pages"],
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

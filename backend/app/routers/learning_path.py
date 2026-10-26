from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import PDFDocument, LearningPath, TopicExplanation, ProgressLog, User
from app.schemas import (
    LearningPathOut,
    LearningTopic,
    ExplainTopicRequest,
    ExplainTopicResponse,
)
from app.services.auth_service import get_current_user
from app.services.ai_service import AIService, AIServiceError

router = APIRouter(prefix="/pdf", tags=["Learning Path"])


@router.get(
    "/{pdf_id}/learning-path",
    response_model=LearningPathOut,
    summary="Get or generate a structured learning path for a PDF",
    responses={
        200: {"description": "Structured learning path successfully returned or generated."},
        404: {"description": "PDF document not found."},
        403: {"description": "Access forbidden for this document."},
        503: {"description": "AI service temporarily unavailable due to high demand."},
        504: {"description": "AI service request timed out."},
    },
)
def get_learning_path(
    pdf_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the structured learning roadmap for the specified PDF.
    If not already generated, analyzes the document with Gemini AI to generate one.
    """
    pdf = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF with ID {pdf_id} not found.",
        )

    if pdf.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this PDF document.",
        )

    # Return existing learning path if already generated
    learning_path = db.query(LearningPath).filter(LearningPath.pdf_id == pdf.id).first()
    if learning_path:
        return learning_path

    # Generate with AI
    try:
        ai_data = AIService.generate_learning_path(pdf=pdf, db=db)
    except AIServiceError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        )

    topics_list = ai_data.get("topics", [])

    new_path = LearningPath(
        pdf_id=pdf.id,
        title=ai_data.get("title", f"{pdf.title} - Learning Roadmap"),
        overview=ai_data.get("overview", "Generated learning path from document chapters."),
        estimated_hours=float(ai_data.get("estimated_hours", 2.0)),
        topics=topics_list,
    )
    db.add(new_path)

    # Record progress log
    log = ProgressLog(
        user_id=current_user.id,
        activity_type="learning_path_generated",
        subject=pdf.title,
        metadata_json={"pdf_id": pdf.id, "topics_count": len(topics_list)},
    )
    db.add(log)

    db.commit()
    db.refresh(new_path)
    return new_path


@router.post(
    "/{pdf_id}/explain",
    response_model=ExplainTopicResponse,
    summary="Get an AI teacher explanation for a specific topic in a PDF",
)
def explain_topic(
    pdf_id: int,
    request: ExplainTopicRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a personalized, depth-tailored explanation of a topic using
    the PDF's extracted content and Gemini AI.
    """
    pdf = db.query(PDFDocument).filter(PDFDocument.id == pdf_id).first()
    if not pdf:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PDF with ID {pdf_id} not found.",
        )

    if pdf.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this PDF document.",
        )

    try:
        explanation_text = AIService.explain_topic(
            pdf=pdf,
            topic=request.topic,
            depth=request.depth or "beginner",
            db=db,
        )
    except AIServiceError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=e.message,
        )

    # Save explanation history
    explanation_record = TopicExplanation(
        pdf_id=pdf.id,
        user_id=current_user.id,
        topic=request.topic,
        depth=request.depth or "beginner",
        content=explanation_text,
    )
    db.add(explanation_record)

    # Log progress
    log = ProgressLog(
        user_id=current_user.id,
        activity_type="topic_explained",
        subject=f"{pdf.title}: {request.topic}",
    )
    db.add(log)

    db.commit()

    return ExplainTopicResponse(
        topic=request.topic,
        depth=request.depth or "beginner",
        explanation=explanation_text,
        pdf_id=pdf.id,
    )

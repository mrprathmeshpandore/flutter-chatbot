from collections import defaultdict
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import PDFDocument, QuizSubmission, ProgressLog, LearningPath, User
from app.schemas import (
    ProgressSummaryOut,
    ActivityLogItem,
    SubjectsProgressOut,
    SubjectProgressItem,
)
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/progress", tags=["Progress & Analytics"])


@router.get(
    "/summary",
    response_model=ProgressSummaryOut,
    summary="Get overall learning progress summary",
)
def get_progress_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns high-level statistics for the student: total PDFs studied,
    quizzes completed, average score, and recent learning events.
    """
    total_pdfs = (
        db.query(func.count(PDFDocument.id))
        .filter(PDFDocument.owner_id == current_user.id)
        .scalar()
        or 0
    )

    submissions = (
        db.query(QuizSubmission)
        .filter(QuizSubmission.user_id == current_user.id)
        .all()
    )
    total_quizzes = len(submissions)
    avg_score = (
        round(sum(s.percentage for s in submissions) / total_quizzes, 1)
        if total_quizzes > 0
        else 0.0
    )

    learning_paths_count = (
        db.query(func.count(LearningPath.id))
        .join(PDFDocument, LearningPath.pdf_id == PDFDocument.id)
        .filter(PDFDocument.owner_id == current_user.id)
        .scalar()
        or 0
    )

    recent_logs = (
        db.query(ProgressLog)
        .filter(ProgressLog.user_id == current_user.id)
        .order_by(ProgressLog.created_at.desc())
        .limit(10)
        .all()
    )

    return ProgressSummaryOut(
        total_pdfs=total_pdfs,
        total_quizzes_taken=total_quizzes,
        average_quiz_score=avg_score,
        learning_paths_count=learning_paths_count,
        recent_activity=[
            ActivityLogItem(
                activity_type=l.activity_type,
                subject=l.subject,
                score=l.score,
                created_at=l.created_at,
            )
            for l in recent_logs
        ],
    )


@router.get(
    "/subjects",
    response_model=SubjectsProgressOut,
    summary="Get breakdown of learning performance by subject/document",
)
def get_subject_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Groups quizzes, study activities, and scores by subject or PDF.
    """
    # 1. Fetch user PDFs
    user_pdfs = (
        db.query(PDFDocument)
        .filter(PDFDocument.owner_id == current_user.id)
        .all()
    )
    pdf_map = {p.id: p.title for p in user_pdfs}

    # 2. Fetch all user quiz submissions with their quiz info
    submissions = (
        db.query(QuizSubmission)
        .filter(QuizSubmission.user_id == current_user.id)
        .order_by(QuizSubmission.submitted_at.desc())
        .all()
    )

    subject_data: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"pdf_id": None, "scores": [], "last_activity": None}
    )

    # Initialize with all uploaded PDFs so they appear even if not quizzed yet
    for p in user_pdfs:
        subject_data[p.title]["pdf_id"] = p.id
        subject_data[p.title]["last_activity"] = p.uploaded_at

    for sub in submissions:
        quiz = sub.quiz
        subject_name = quiz.topic or (pdf_map.get(quiz.pdf_id) if quiz.pdf_id else "General Studies")
        if quiz.pdf_id:
            subject_data[subject_name]["pdf_id"] = quiz.pdf_id

        subject_data[subject_name]["scores"].append(sub.percentage)
        if (
            not subject_data[subject_name]["last_activity"]
            or sub.submitted_at > subject_data[subject_name]["last_activity"]
        ):
            subject_data[subject_name]["last_activity"] = sub.submitted_at

    items: List[SubjectProgressItem] = []
    for subject, data in subject_data.items():
        scores = data["scores"]
        avg = round(sum(scores) / len(scores), 1) if scores else 0.0
        if data["last_activity"]:
            items.append(
                SubjectProgressItem(
                    subject=subject,
                    pdf_id=data["pdf_id"],
                    quizzes_taken=len(scores),
                    average_score=avg,
                    last_activity=data["last_activity"],
                )
            )

    items.sort(key=lambda x: x.last_activity, reverse=True)
    return SubjectsProgressOut(subjects=items)

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.schemas import (
    GenerateQuizRequest,
    QuizOut,
    SubmitQuizRequest,
    QuizResultOut,
    QuizHistoryItem,
)
from app.services.auth_service import get_current_user
from app.services.quiz_service import QuizService

router = APIRouter(prefix="/quiz", tags=["Quiz"])


@router.post(
    "/generate",
    response_model=QuizOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an interactive multiple-choice quiz",
)
def generate_quiz(
    request: GenerateQuizRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generates a personalized multiple-choice quiz from either a PDF document or a specific topic.
    """
    quiz = QuizService.generate_quiz(
        user=current_user,
        pdf_id=request.pdf_id,
        topic=request.topic,
        num_questions=request.num_questions,
        difficulty=request.difficulty or "medium",
        db=db,
    )
    return quiz


@router.post(
    "/submit",
    response_model=QuizResultOut,
    summary="Submit answers for evaluation and scoring",
)
def submit_quiz(
    request: SubmitQuizRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluates submitted quiz answers, calculates percentage score, records history,
    and returns question-by-question explanations.
    """
    result = QuizService.submit_quiz(
        user=current_user,
        quiz_id=request.quiz_id,
        answers=request.answers,
        db=db,
    )
    return result


@router.get(
    "/{quiz_id}/results",
    response_model=List[QuizHistoryItem],
    summary="Get past results and score history for a quiz",
)
def get_quiz_results(
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the historical submissions and scores for the specified quiz.
    """
    submissions = QuizService.get_quiz_results(
        user=current_user,
        quiz_id=quiz_id,
        db=db,
    )
    return submissions

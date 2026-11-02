
import logging

from app.database import SessionLocal
from app.models import User
from app.services.quiz_service import QuizService

logger = logging.getLogger(__name__)


def generate_pdf_quiz_task(
    user_id: int,
    pdf_id: int,
):
    """
    Generates a PDF-based quiz in the background.
    Uses an independent database session.
    """

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if not user:
            logger.warning(
                "Quiz generation skipped: User %s not found",
                user_id,
            )
            return

        quiz = QuizService.generate_quiz(
            user=user,
            pdf_id=pdf_id,
            topic=None,
            num_questions=5,
            difficulty="medium",
            db=db,
        )

        logger.info(
            "Background quiz generated successfully. "
            "Quiz ID: %s, PDF ID: %s",
            quiz.id,
            pdf_id,
        )

    except Exception:
        db.rollback()
        logger.exception(
            "Background quiz generation failed for PDF ID: %s",
            pdf_id,
        )

    finally:
        db.close()

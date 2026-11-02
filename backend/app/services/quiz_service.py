
import json
import logging
from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import (
    Quiz,
    QuizQuestion,
    QuizSubmission,
    ProgressLog,
    PDFDocument,
    PDFPage,
    User,
)
from app.schemas import (
    QuizAnswerItem,
    QuizResultOut,
    SubmittedAnswerDetail,
)
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


class QuizService:

    @classmethod
    def generate_quiz(
        cls,
        user: User,
        pdf_id: Optional[int],
        topic: Optional[str],
        num_questions: int,
        difficulty: str,
        db: Session,
        force_refresh: bool = False,
    ) -> Quiz:

        source_context = ""
        pdf = None

        quiz_title = f"{topic or 'General Knowledge'} Quiz"

        # Check if an unattempted quiz with enough questions already exists for this pdf and difficulty
        if pdf_id and not force_refresh:
            existing_quiz = (
                db.query(Quiz)
                .filter(
                    Quiz.pdf_id == pdf_id,
                    Quiz.user_id == user.id,
                    Quiz.difficulty == difficulty,
                )
                .order_by(Quiz.id.desc())
                .first()
            )
            if existing_quiz and len(existing_quiz.questions) >= num_questions:
                has_submission = (
                    db.query(QuizSubmission.id)
                    .filter(QuizSubmission.quiz_id == existing_quiz.id)
                    .first()
                )
                if not has_submission:
                    logger.info(
                        "Reusing existing unattempted quiz id=%s for user=%s, pdf=%s",
                        existing_quiz.id,
                        user.id,
                        pdf_id,
                    )
                    return existing_quiz

        # 1. Get PDF Details
        if pdf_id:
            pdf = (
                db.query(PDFDocument)
                .filter(
                    PDFDocument.id == pdf_id,
                    PDFDocument.owner_id == user.id,
                )
                .first()
            )

            if not pdf:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="PDF document not found.",
                )

            quiz_title = f"{pdf.title} Quiz"

            pages = (
                db.query(PDFPage)
                .filter(PDFPage.pdf_id == pdf.id)
                .order_by(PDFPage.page_number)
                .limit(10)
                .all()
            )

            source_context = "\n\n".join(
                [
                    f"Page {p.page_number}: {p.text_content[:600]}"
                    for p in pages
                ]
            )

        # 2. Get Previously Generated Questions
        previous_questions = []

        if pdf_id:
            previous_questions = [
                row[0]
                for row in (
                    db.query(QuizQuestion.question_text)
                    .join(Quiz, QuizQuestion.quiz_id == Quiz.id)
                    .filter(
                        Quiz.pdf_id == pdf_id,
                        Quiz.user_id == user.id,
                    )
                    .all()
                )
            ]

        previous_questions_text = "\n".join(
            f"- {question}"
            for question in previous_questions
        )

        # 3. Prepare AI Prompt
        prompt = f"""
You are an expert educational examiner.

Create exactly {num_questions} multiple-choice questions.

TOPIC: {topic or (pdf.title if pdf else 'General Science and Math')}

DIFFICULTY: {difficulty}

SOURCE CONTENT:
{source_context[:3500] if source_context else "Generate educational questions on this topic."}

PREVIOUSLY GENERATED QUESTIONS:
{previous_questions_text or "No previous questions."}

IMPORTANT RULES:
- Never repeat previously generated questions.
- Do not rephrase old questions with minor word changes.
- Test different concepts, facts, and applications.
- Generate exactly {num_questions} unique questions.
- Every question must have exactly 4 options.
- correct_option must be an integer between 0 and 3.

Return ONLY valid JSON in this format:

{{
    "title": "{quiz_title}",
    "questions": [
        {{
            "question_text": "Question here?",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_option": 0,
            "explanation": "Explanation here."
        }}
    ]
}}
"""

        # 4. Generate Questions Using AI
        try:
            response_text = AIService.generate_text(prompt)
            generated_json = AIService._extract_json(response_text)

        except Exception:
            logger.exception("AI quiz generation failed.")

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI could not generate the quiz. Please try again.",
            )

        # 5. Validate AI Response
        questions_data = []

        if not isinstance(generated_json, dict):
            generated_json = {}

        generated_questions = generated_json.get("questions", [])

        if not isinstance(generated_questions, list):
            generated_questions = []

        seen_questions = {
            question.strip().lower()
            for question in previous_questions
        }

        for q in generated_questions:

            if len(questions_data) >= num_questions:
                break

            if not isinstance(q, dict):
                continue

            question_text = q.get("question_text", "")
            options = q.get("options", [])
            correct_option = q.get("correct_option", 0)

            if not isinstance(question_text, str):
                continue

            question_text = question_text.strip()

            if not question_text:
                continue

            normalized_question = question_text.lower()

            # Avoid duplicate questions
            if normalized_question in seen_questions:
                continue

            if normalized_question in {
                item["question_text"].lower()
                for item in questions_data
            }:
                continue

            if not isinstance(options, list) or len(options) != 4:
                continue

            if not all(isinstance(option, str) for option in options):
                continue

            if (
                not isinstance(correct_option, int)
                or isinstance(correct_option, bool)
                or correct_option < 0
                or correct_option > 3
            ):
                continue

            seen_questions.add(normalized_question)

            questions_data.append({
                "question_text": question_text,
                "options": options,
                "correct_option": correct_option,
                "explanation": q.get("explanation", ""),
            })

        # 6. Do Not Save Fake Or Incomplete Questions
        if len(questions_data) != num_questions:

            logger.warning(
                "Quiz generation incomplete. Expected %s questions, got %s.",
                num_questions,
                len(questions_data),
            )

            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Could not generate enough unique questions. Please try again.",
            )

        # 7. Save Quiz In Database
        quiz = Quiz(
            user_id=user.id,
            pdf_id=pdf_id,
            title=quiz_title,
            topic=topic or (pdf.title if pdf else "General"),
            difficulty=difficulty,
            total_questions=len(questions_data),
        )

        db.add(quiz)
        db.flush()

        for q_data in questions_data:

            quiz_question = QuizQuestion(
                quiz_id=quiz.id,
                question_text=q_data["question_text"],
                options=q_data["options"],
                correct_option=q_data["correct_option"],
                explanation=q_data["explanation"],
            )

            db.add(quiz_question)

        db.commit()
        db.refresh(quiz)

        return quiz

    @classmethod
    def submit_quiz(
        cls,
        user: User,
        quiz_id: int,
        answers: List[QuizAnswerItem],
        db: Session,
    ) -> QuizResultOut:

        quiz = (
            db.query(Quiz)
            .filter(Quiz.id == quiz_id)
            .first()
        )

        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found.",
            )

        if quiz.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this quiz.",
            )

        questions = (
            db.query(QuizQuestion)
            .filter(QuizQuestion.quiz_id == quiz.id)
            .order_by(QuizQuestion.id)
            .all()
        )

        if not questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This quiz has no questions.",
            )

        question_map = {q.id: q for q in questions}

        answer_map = {}

        for answer in answers:

            if answer.question_id not in question_map:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid question ID in submitted answers.",
                )

            if answer.question_id in answer_map:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Duplicate answer submitted for a question.",
                )

            answer_map[answer.question_id] = answer.selected_option

        correct_count = 0
        details = []
        submission_json = []

        for question in questions:

            selected = answer_map.get(question.id, -1)

            is_correct = selected == question.correct_option

            if is_correct:
                correct_count += 1

            details.append(
                SubmittedAnswerDetail(
                    question_id=question.id,
                    question_text=question.question_text,
                    options=question.options,
                    selected_option=selected,
                    correct_option=question.correct_option,
                    is_correct=is_correct,
                    explanation=question.explanation,
                )
            )

            submission_json.append({
                "question_id": question.id,
                "selected_option": selected,
                "correct_option": question.correct_option,
                "is_correct": is_correct,
            })

        total = len(questions)

        percentage = round(
            (correct_count / total) * 100.0,
            1,
        )

        submission = QuizSubmission(
            quiz_id=quiz.id,
            user_id=user.id,
            score=float(correct_count),
            total_questions=total,
            correct_answers=correct_count,
            percentage=percentage,
            submitted_answers=submission_json,
        )

        db.add(submission)

        log = ProgressLog(
            user_id=user.id,
            pdf_id=quiz.pdf_id,
            activity_type="quiz_completed",
            subject=quiz.topic or quiz.title,
            score=percentage,
            metadata_json={
                "quiz_id": quiz.id,
                "pdf_id": quiz.pdf_id,
                "submission_id": None,
            },
        )

        db.add(log)

        db.commit()
        db.refresh(submission)

        return QuizResultOut(
            submission_id=submission.id,
            quiz_id=quiz.id,
            quiz_title=quiz.title,
            score=float(correct_count),
            total_questions=total,
            correct_answers=correct_count,
            percentage=percentage,
            submitted_at=submission.submitted_at,
            details=details,
        )

    @classmethod
    def get_quiz_results(
        cls,
        user: User,
        quiz_id: int,
        db: Session,
    ) -> List[QuizSubmission]:

        quiz = (
            db.query(Quiz)
            .filter(Quiz.id == quiz_id)
            .first()
        )

        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quiz not found.",
            )

        if quiz.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this quiz's results.",
            )

        return (
            db.query(QuizSubmission)
            .filter(
                QuizSubmission.quiz_id == quiz_id,
                QuizSubmission.user_id == user.id,
            )
            .order_by(QuizSubmission.submitted_at.desc())
            .all()
        )

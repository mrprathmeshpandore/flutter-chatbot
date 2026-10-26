import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models import Quiz, QuizQuestion, QuizSubmission, ProgressLog, PDFDocument, PDFPage, User
from app.schemas import QuizAnswerItem, QuizResultOut, SubmittedAnswerDetail
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
    ) -> Quiz:
        """
        Generates a customized multiple-choice quiz using Gemini AI based on
        either a PDF's content or a specified topic.
        """
        source_context = ""
        quiz_title = f"{topic or 'General Knowledge'} Quiz"

        if pdf_id:
            pdf = db.query(PDFDocument).filter(PDFDocument.id == pdf_id, PDFDocument.owner_id == user.id).first()
            if not pdf:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Specified PDF document not found or does not belong to you.",
                )
            quiz_title = f"{pdf.title} Quiz"
            # Gather content from PDF pages
            pages = db.query(PDFPage).filter(PDFPage.pdf_id == pdf.id).order_by(PDFPage.page_number).limit(10).all()
            source_context = "\n\n".join([f"Page {p.page_number}: {p.text_content[:600]}" for p in pages])

        prompt = f"""
You are an expert educational examiner. Create a {num_questions}-question multiple-choice quiz.

TOPIC: {topic or (pdf.title if pdf_id else 'General Science and Math')}
DIFFICULTY LEVEL: {difficulty}
SOURCE CONTENT:
{source_context[:3500] if source_context else "Generate balanced, insightful educational questions on this topic."}

Return ONLY valid JSON (no surrounding markdown or chat) with this schema:
{{
  "title": "{quiz_title}",
  "questions": [
    {{
      "question_text": "What is the primary function of...?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_option": 0,
      "explanation": "Brief explanation of why Option A is correct."
    }}
  ]
}}
Ensure 'correct_option' is an integer between 0 and 3 matching the index of the correct answer in the options list. Provide exactly {num_questions} questions.
"""
        generated_json = None
        try:
            response_text = AIService.generate_text(prompt)
            generated_json = AIService._extract_json(response_text)
        except Exception as e:
            logger.warning(f"AI quiz generation failed, falling back to structured template: {e}")

        # Validate or fallback
        questions_data = []
        if generated_json and "questions" in generated_json and len(generated_json["questions"]) > 0:
            for q in generated_json["questions"][:num_questions]:
                opts = q.get("options", [])
                if len(opts) >= 2:
                    # Pad to 4 options if needed
                    while len(opts) < 4:
                        opts.append(f"Option {len(opts) + 1}")
                    correct_idx = q.get("correct_option", 0)
                    if not isinstance(correct_idx, int) or correct_idx < 0 or correct_idx >= len(opts):
                        correct_idx = 0
                    questions_data.append({
                        "question_text": q.get("question_text", "Sample Question"),
                        "options": opts[:4],
                        "correct_option": correct_idx,
                        "explanation": q.get("explanation", "Correct based on the material."),
                    })

        # Fallback if no questions parsed
        if not questions_data:
            base_topic = topic or (pdf.title if pdf_id else "Core Concepts")
            for i in range(1, num_questions + 1):
                questions_data.append({
                    "question_text": f"Question {i}: Which of the following best describes a key principle of {base_topic}?",
                    "options": [
                        f"Fundamental component {i} of the subject",
                        "An unrelated historical principle",
                        "A disproven hypothesis",
                        "None of the above",
                    ],
                    "correct_option": 0,
                    "explanation": f"Option 1 accurately reflects the core principle of {base_topic}.",
                })

        # Save to DB
        quiz = Quiz(
            user_id=user.id,
            pdf_id=pdf_id,
            title=quiz_title,
            topic=topic or (pdf.title if pdf_id else "General"),
            difficulty=difficulty,
            total_questions=len(questions_data),
        )
        db.add(quiz)
        db.flush()

        for q_data in questions_data:
            quiz_q = QuizQuestion(
                quiz_id=quiz.id,
                question_text=q_data["question_text"],
                options=q_data["options"],
                correct_option=q_data["correct_option"],
                explanation=q_data.get("explanation"),
            )
            db.add(quiz_q)

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
        """
        Evaluates submitted answers, scores the quiz, creates a submission record,
        and logs the student's progress.
        """
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz with ID {quiz_id} not found.",
            )

        # Enforce user ownership of the quiz
        if quiz.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this quiz.",
            )

        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz.id).order_by(QuizQuestion.id).all()
        if not questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This quiz has no questions.",
            )

        question_map = {q.id: q for q in questions}
        answer_map = {a.question_id: a.selected_option for a in answers}

        correct_count = 0
        details: List[SubmittedAnswerDetail] = []
        submission_json = []

        for q in questions:
            selected = answer_map.get(q.id, -1)  # -1 if unanswered
            is_correct = (selected == q.correct_option)
            if is_correct:
                correct_count += 1

            detail = SubmittedAnswerDetail(
                question_id=q.id,
                question_text=q.question_text,
                options=q.options,
                selected_option=selected,
                correct_option=q.correct_option,
                is_correct=is_correct,
                explanation=q.explanation,
            )
            details.append(detail)

            submission_json.append({
                "question_id": q.id,
                "selected_option": selected,
                "correct_option": q.correct_option,
                "is_correct": is_correct,
            })

        total = len(questions)
        percentage = round((correct_count / total) * 100.0, 1)

        # Record submission
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

        # Record progress log
        log = ProgressLog(
            user_id=user.id,
            activity_type="quiz_completed",
            subject=quiz.topic or quiz.title,
            score=percentage,
            metadata_json={"quiz_id": quiz.id, "submission_id": None},
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
        """
        Retrieves all past submissions for a specific quiz.
        """
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quiz with ID {quiz_id} not found.",
            )

        if quiz.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this quiz's results.",
            )

        return db.query(QuizSubmission).filter(
            QuizSubmission.quiz_id == quiz_id,
            QuizSubmission.user_id == user.id,
        ).order_by(QuizSubmission.submitted_at.desc()).all()

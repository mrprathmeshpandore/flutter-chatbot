import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, PDFDocument, TopicExplanation, Quiz, QuizQuestion, QuizSubmission
from app.services.ai_service import (
    AIService,
    AIServiceRateLimitError,
    AIServiceUnavailableError,
    is_transient_gemini_error,
    ai_cache,
)
from app.services.quiz_service import QuizService


def test_error_classification_daily_vs_rpm():
    """Verify rate limit classifier differentiates daily quota (RPD) from transient burst (RPM)."""
    # Daily quota with retryDelay > 60
    err_daily_1 = Exception(
        "Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, "
        "limit: 20, model: gemini-3.6-flash, retryDelay: 74471s"
    )
    is_transient, code, reason = is_transient_gemini_error(err_daily_1)
    assert is_transient is False
    assert code == 429
    assert reason == "DAILY_QUOTA_EXHAUSTED"

    # Daily quota with text indicator
    err_daily_2 = Exception("Resource exhausted: 15 requests per day limit exceeded")
    is_transient, code, reason = is_transient_gemini_error(err_daily_2)
    assert is_transient is False
    assert code == 429
    assert reason == "DAILY_QUOTA_EXHAUSTED"

    # Transient burst RPM with small retryDelay
    err_rpm = Exception("RESOURCE_EXHAUSTED: Rate limit exceeded. Please retry in retryDelay: 3s")
    is_transient, code, reason = is_transient_gemini_error(err_rpm)
    assert is_transient is True
    assert code == 429
    assert reason == "RPM_RATE_LIMIT"

    # Transient 503
    err_503 = Exception("503 Service Unavailable: High demand")
    is_transient, code, reason = is_transient_gemini_error(err_503)
    assert is_transient is True
    assert code == 503


def test_ai_cache_hit_prevents_api_call(db_session: Session, test_user: User):
    """Verify that cached questions return instantly without calling Gemini API."""
    ai_cache.clear()
    call_count = 0

    def mock_gen(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return "This is a freshly generated answer."

    with patch.object(AIService, "generate_text", side_effect=mock_gen):
        # 1. First call: Cache miss -> invokes generate_text
        res1 = AIService.ask_ai_teacher(
            question="What is backpropagation?",
            pdf=None,
            db=db_session,
            user_id=test_user.id,
        )
        assert res1["answer"] == "This is a freshly generated answer."
        assert call_count == 1

        # 2. Second identical call: Cache hit -> does NOT invoke generate_text
        res2 = AIService.ask_ai_teacher(
            question="What is backpropagation?",
            pdf=None,
            db=db_session,
            user_id=test_user.id,
        )
        assert res2["answer"] == "This is a freshly generated answer."
        assert call_count == 1  # Still 1!


def test_ai_cache_user_isolation(db_session: Session, test_user: User, second_user: User):
    """Verify User 1 and User 2 have strictly isolated cache namespaces."""
    ai_cache.clear()

    # Seed User 1's cache
    ai_cache.set(
        user_id=test_user.id,
        pdf_id=None,
        operation="ask_ai",
        query="What is gradient descent?",
        model="gemini-flash-lite-latest",
        value={"answer": "User 1 personalized answer"},
    )

    # User 1 cache hit
    cached_user1 = ai_cache.get(
        user_id=test_user.id,
        pdf_id=None,
        operation="ask_ai",
        query="What is gradient descent?",
        model="gemini-flash-lite-latest",
    )
    assert cached_user1 is not None
    assert cached_user1["answer"] == "User 1 personalized answer"

    # User 2 cache miss (strict isolation)
    cached_user2 = ai_cache.get(
        user_id=second_user.id,
        pdf_id=None,
        operation="ask_ai",
        query="What is gradient descent?",
        model="gemini-flash-lite-latest",
    )
    assert cached_user2 is None


def test_ai_cache_invalidation_by_pdf(db_session: Session, test_user: User):
    """Verify that deleting or invalidating a PDF flushes its cache."""
    ai_cache.clear()
    pdf_id = 999

    ai_cache.set(
        user_id=test_user.id,
        pdf_id=pdf_id,
        operation="ask_ai",
        query="Explain chapter 1",
        model="gemini-flash-lite-latest",
        value={"answer": "Chapter 1 content"},
    )

    # Assert entry exists
    assert ai_cache.get(test_user.id, pdf_id, "ask_ai", "Explain chapter 1", "gemini-flash-lite-latest") is not None

    # Invalidate PDF
    deleted_count = AIService.invalidate_pdf_cache(pdf_id)
    assert deleted_count == 1

    # Assert entry is gone
    assert ai_cache.get(test_user.id, pdf_id, "ask_ai", "Explain chapter 1", "gemini-flash-lite-latest") is None


@pytest.mark.disable_mock_gemini
def test_daily_quota_exhaustion_does_not_retry():
    """Verify that daily quota exhaustion halts retries immediately without sleeping."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception(
        "Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, retryDelay: 74471s"
    )

    with patch.object(AIService, "get_client", return_value=mock_client), \
         patch("app.services.ai_service.settings.GEMINI_API_KEY", "mock_key"), \
         patch("app.services.ai_service.settings.GEMINI_FALLBACK_MODEL", None), \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(AIServiceRateLimitError) as exc_info:
            AIService.generate_text("Test prompt")

        assert exc_info.value.status_code == 429
        assert exc_info.value.is_daily_exhaustion is True
        assert "daily" in exc_info.value.message.lower()
        # Ensure it was called only once and did NOT sleep/retry
        assert mock_client.models.generate_content.call_count == 1
        assert mock_sleep.call_count == 0


@pytest.mark.disable_mock_gemini
def test_model_fallback_mechanism():
    """Verify that if primary model fails with 503 or 404, fallback model is attempted."""
    mock_client = MagicMock()

    def side_effect(model, contents, **kwargs):
        if model == "gemini-flash-lite-latest":
            raise Exception("503 Service Unavailable: High demand on flash-lite")
        elif model == "gemini-3.5-flash-lite":
            mock_res = MagicMock()
            mock_res.text = "Fallback model response succeeded!"
            return mock_res
        raise Exception(f"Unexpected model: {model}")

    mock_client.models.generate_content.side_effect = side_effect

    with patch.object(AIService, "get_client", return_value=mock_client), \
         patch("app.services.ai_service.settings.GEMINI_API_KEY", "mock_key"), \
         patch("app.services.ai_service.settings.GEMINI_MODEL", "gemini-flash-lite-latest"), \
         patch("app.services.ai_service.settings.GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite"), \
         patch("app.services.ai_service.settings.GEMINI_MAX_RETRIES", 0):
        result = AIService.generate_text("Test prompt")
        assert result == "Fallback model response succeeded!"


def test_explain_topic_reuses_db_explanation(client: TestClient, db_session: Session, test_user: User, auth_headers):
    """Verify that explain_topic returns existing DB record without calling Gemini."""
    # Create test PDF
    pdf = PDFDocument(
        owner_id=test_user.id,
        title="Physics Book",
        filename="physics.pdf",
        file_path="/tmp/physics.pdf",
        file_size=2048,
        page_count=10,
    )
    db_session.add(pdf)
    db_session.commit()
    db_session.refresh(pdf)

    # Insert existing TopicExplanation in DB
    existing_explanation = TopicExplanation(
        pdf_id=pdf.id,
        user_id=test_user.id,
        topic="Thermodynamics",
        depth="beginner",
        content="Previously generated thermodynamics explanation.",
    )
    db_session.add(existing_explanation)
    db_session.commit()

    call_count = 0
    def mock_explain(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return "New AI explanation"

    with patch.object(AIService, "explain_topic", side_effect=mock_explain):
        response = client.post(
            f"/pdf/{pdf.id}/explain",
            headers=auth_headers,
            json={"topic": "Thermodynamics", "depth": "beginner"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["explanation"] == "Previously generated thermodynamics explanation."
        # Gemini was NOT called!
        assert call_count == 0


def test_quiz_deduplication_reuses_unattempted_quiz(db_session: Session, test_user: User):
    """Verify that QuizService reuses existing unattempted quiz for the same PDF and difficulty."""
    pdf = PDFDocument(
        owner_id=test_user.id,
        title="Chemistry Guide",
        filename="chem.pdf",
        file_path="/tmp/chem.pdf",
        file_size=1024,
        page_count=5,
    )
    db_session.add(pdf)
    db_session.commit()
    db_session.refresh(pdf)

    # Create unattempted quiz with 3 questions
    quiz = Quiz(
        user_id=test_user.id,
        pdf_id=pdf.id,
        title="Chemistry Guide Quiz",
        difficulty="medium",
        total_questions=3,
    )
    db_session.add(quiz)
    db_session.commit()
    db_session.refresh(quiz)

    for i in range(3):
        q = QuizQuestion(
            quiz_id=quiz.id,
            question_text=f"Sample Question {i+1}",
            options=["A", "B", "C", "D"],
            correct_option=0,
            explanation=f"Explanation {i+1}",
        )
        db_session.add(q)
    db_session.commit()

    call_count = 0
    def mock_generate(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return "{}"

    with patch.object(AIService, "generate_text", side_effect=mock_generate):
        # Request quiz for same PDF and difficulty
        reused_quiz = QuizService.generate_quiz(
            user=test_user,
            pdf_id=pdf.id,
            topic=None,
            num_questions=3,
            difficulty="medium",
            db=db_session,
        )
        assert reused_quiz.id == quiz.id
        assert call_count == 0  # Zero Gemini calls!

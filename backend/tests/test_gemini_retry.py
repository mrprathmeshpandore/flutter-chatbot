import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from app.config import settings
from app.services.ai_service import (
    AIService,
    AIServiceError,
    AIServiceUnavailableError,
    AIServiceConfigurationError,
    is_transient_gemini_error,
    sanitize_gemini_error,
)
from app.models import LearningPath


class MockContentResponse:
    def __init__(self, text: str):
        self.text = text


@pytest.mark.disable_mock_gemini
def test_is_transient_gemini_error_detection():
    """Verify classification of transient (429, 500, 503) vs non-transient (400, 401, 404) errors."""
    # Transient 503
    err_503 = genai_errors.ServerError(503, {"error": {"code": 503, "message": "High demand", "status": "UNAVAILABLE"}})
    is_transient, code, reason = is_transient_gemini_error(err_503)
    assert is_transient is True
    assert code == 503

    # Transient 429
    err_429 = genai_errors.ClientError(429, {"error": {"code": 429, "message": "Rate limit", "status": "RESOURCE_EXHAUSTED"}})
    is_transient, code, reason = is_transient_gemini_error(err_429)
    assert is_transient is True
    assert code == 429

    # Transient 500
    err_500 = genai_errors.ServerError(500, {"error": {"code": 500, "message": "Internal error", "status": "INTERNAL"}})
    is_transient, code, reason = is_transient_gemini_error(err_500)
    assert is_transient is True
    assert code == 500

    # Non-transient 404
    err_404 = genai_errors.ClientError(404, {"error": {"code": 404, "message": "Model not found", "status": "NOT_FOUND"}})
    is_transient, code, reason = is_transient_gemini_error(err_404)
    assert is_transient is False
    assert code == 404

    # Non-transient 401
    err_401 = genai_errors.ClientError(401, {"error": {"code": 401, "message": "API key invalid", "status": "UNAUTHENTICATED"}})
    is_transient, code, reason = is_transient_gemini_error(err_401)
    assert is_transient is False
    assert code == 401

    # Non-transient 400
    err_400 = genai_errors.ClientError(400, {"error": {"code": 400, "message": "Bad arguments", "status": "INVALID_ARGUMENT"}})
    is_transient, code, reason = is_transient_gemini_error(err_400)
    assert is_transient is False
    assert code == 400


@pytest.mark.disable_mock_gemini
def test_sanitize_gemini_error_redacts_keys():
    """Verify that sensitive API keys and tokens are never exposed in log/error strings."""
    secret_key = "AIzaSySecretTestKey1234567890"
    original_key = settings.GEMINI_API_KEY
    try:
        settings.GEMINI_API_KEY = secret_key
        raw_msg = f"Failed request to https://generativelanguage.googleapis.com/v1beta?key={secret_key} with Bearer {secret_key}"
        sanitized = sanitize_gemini_error(raw_msg)
        assert secret_key not in sanitized
        assert "[REDACTED" in sanitized
    finally:
        settings.GEMINI_API_KEY = original_key


@pytest.mark.disable_mock_gemini
def test_generate_text_success_on_first_attempt(monkeypatch):
    """Verify successful generation without retry when Gemini responds normally."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MockContentResponse("AI response content")
    monkeypatch.setattr(AIService, "get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    result = AIService.generate_text("Explain photosynthesis")
    assert result == "AI response content"
    assert mock_client.models.generate_content.call_count == 1


@pytest.mark.disable_mock_gemini
def test_generate_text_retry_on_503_then_success(monkeypatch):
    """Verify bounded retry with exponential backoff and jitter recovers from a transient 503."""
    mock_client = MagicMock()
    err_503 = genai_errors.ServerError(503, {"error": {"code": 503, "message": "High demand", "status": "UNAVAILABLE"}})
    mock_client.models.generate_content.side_effect = [
        err_503,
        MockContentResponse("Recovered response"),
    ]
    monkeypatch.setattr(AIService, "get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    # Speed up delays for unit test
    monkeypatch.setattr(settings, "GEMINI_INITIAL_RETRY_DELAY", 0.001)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRY_DELAY", 0.005)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", 3)

    result = AIService.generate_text("Test prompt")
    assert result == "Recovered response"
    assert mock_client.models.generate_content.call_count == 2


@pytest.mark.disable_mock_gemini
def test_generate_text_retry_on_429_then_success(monkeypatch):
    """Verify bounded retry recovers from transient 429 rate limit."""
    mock_client = MagicMock()
    err_429 = genai_errors.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded", "status": "RESOURCE_EXHAUSTED"}})
    mock_client.models.generate_content.side_effect = [
        err_429,
        MockContentResponse("Success after rate limit"),
    ]
    monkeypatch.setattr(AIService, "get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_INITIAL_RETRY_DELAY", 0.001)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRY_DELAY", 0.005)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", 3)

    result = AIService.generate_text("Test prompt")
    assert result == "Success after rate limit"
    assert mock_client.models.generate_content.call_count == 2


@pytest.mark.disable_mock_gemini
def test_generate_text_exhausted_retries_raises_503(monkeypatch):
    """Verify that retries are bounded and raise AIServiceUnavailableError when exhausted."""
    mock_client = MagicMock()
    err_503 = genai_errors.ServerError(503, {"error": {"code": 503, "message": "High demand", "status": "UNAVAILABLE"}})
    mock_client.models.generate_content.side_effect = err_503
    monkeypatch.setattr(AIService, "get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_INITIAL_RETRY_DELAY", 0.001)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRY_DELAY", 0.005)
    max_retries = 3
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", max_retries)

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        AIService.generate_text("Test prompt")

    assert exc_info.value.status_code == 503
    assert "temporarily unavailable" in exc_info.value.message.lower()
    # 1 initial attempt + 3 retries = 4 calls total (bounded, no indefinite retry)
    assert mock_client.models.generate_content.call_count == max_retries + 1


@pytest.mark.disable_mock_gemini
def test_generate_text_non_transient_404_fails_immediately_without_retry(monkeypatch):
    """Verify that 404 (e.g. invalid/deprecated model ID) fails fast and does not retry."""
    mock_client = MagicMock()
    err_404 = genai_errors.ClientError(404, {"error": {"code": 404, "message": "Model not found", "status": "NOT_FOUND"}})
    mock_client.models.generate_content.side_effect = err_404
    monkeypatch.setattr(AIService, "get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", 3)

    with pytest.raises(AIServiceConfigurationError) as exc_info:
        AIService.generate_text("Test prompt")

    assert exc_info.value.status_code == 502
    assert "not available or supported" in exc_info.value.message.lower()
    # Must fail immediately after 1 call; must NOT retry
    assert mock_client.models.generate_content.call_count == 1


@pytest.mark.disable_mock_gemini
def test_learning_path_endpoint_returns_503_when_gemini_unavailable(
    client: TestClient, auth_headers, sample_pdf_bytes, monkeypatch, db_session
):
    """
    Integration test: When Gemini 503 persists, GET /pdf/{pdf_id}/learning-path
    returns HTTP 503 (not 500), does not fabricate dummy modules, and leaves DB clean.
    """
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("unavailable_doc.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    mock_client = MagicMock()
    err_503 = genai_errors.ServerError(503, {"error": {"code": 503, "message": "High demand", "status": "UNAVAILABLE"}})
    mock_client.models.generate_content.side_effect = err_503
    monkeypatch.setattr(AIService, "get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_INITIAL_RETRY_DELAY", 0.001)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRY_DELAY", 0.005)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", 2)

    response = client.get(f"/pdf/{pdf_id}/learning-path", headers=auth_headers)
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "temporarily unavailable" in detail.lower()
    # Confirm no API keys or internal trace in detail
    assert "test-key" not in detail
    assert "traceback" not in detail.lower()

    # Confirm no fake roadmap was fabricated or committed in the database
    path_in_db = db_session.query(LearningPath).filter(LearningPath.pdf_id == pdf_id).first()
    assert path_in_db is None


@pytest.mark.disable_mock_gemini
def test_learning_path_endpoint_recovers_after_transient_503(
    client: TestClient, auth_headers, sample_pdf_bytes, monkeypatch, db_session
):
    """
    Integration test: Transient 503 is retried, succeeds, returns 200, and persists real path.
    """
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("recover_doc.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    mock_client = MagicMock()
    err_503 = genai_errors.ServerError(503, {"error": {"code": 503, "message": "High demand", "status": "UNAVAILABLE"}})
    valid_roadmap_json = """{
      "title": "Recovered Document Roadmap",
      "overview": "Curated path after transient retry.",
      "estimated_hours": 3.0,
      "topics": [
        {
          "title": "Real Topic 1",
          "description": "Real AI generated description",
          "difficulty": "beginner",
          "estimated_minutes": 30,
          "key_points": ["Point A", "Point B"]
        }
      ]
    }"""
    mock_client.models.generate_content.side_effect = [
        err_503,
        MockContentResponse(valid_roadmap_json),
    ]
    monkeypatch.setattr(AIService, "get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_INITIAL_RETRY_DELAY", 0.001)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRY_DELAY", 0.005)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", 2)

    response = client.get(f"/pdf/{pdf_id}/learning-path", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Recovered Document Roadmap"
    assert data["topics"][0]["title"] == "Real Topic 1"

    # Verify persisted in DB
    path_in_db = db_session.query(LearningPath).filter(LearningPath.pdf_id == pdf_id).first()
    assert path_in_db is not None
    assert path_in_db.title == "Recovered Document Roadmap"


@pytest.mark.disable_mock_gemini
def test_generate_text_timeout_exhausted_retries_raises_504(monkeypatch):
    """Verify that timeout errors (e.g. httpx.ReadTimeout) trigger bounded retries and raise 504."""
    import httpx
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = httpx.ReadTimeout("The read operation timed out")
    monkeypatch.setattr(AIService, "get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_INITIAL_RETRY_DELAY", 0.001)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRY_DELAY", 0.005)
    max_retries = 2
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", max_retries)

    with pytest.raises(AIServiceUnavailableError) as exc_info:
        AIService.generate_text("Test prompt with timeout")

    assert exc_info.value.status_code == 504
    assert "timed out" in exc_info.value.message.lower()
    # 1 initial + 2 retries = 3 calls total
    assert mock_client.models.generate_content.call_count == max_retries + 1


@pytest.mark.disable_mock_gemini
def test_learning_path_endpoint_timeout_returns_504_without_hanging(
    client: TestClient, auth_headers, sample_pdf_bytes, monkeypatch, db_session
):
    """
    Verify that when Gemini requests time out, the endpoint finishes within a bounded
    finite time, returns HTTP 504 (not 500), does not hang, and does not fabricate roadmap.
    """
    import httpx
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("timeout_doc.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = httpx.ReadTimeout("Gateway read timeout")
    monkeypatch.setattr(AIService, "get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_INITIAL_RETRY_DELAY", 0.001)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRY_DELAY", 0.005)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", 2)

    response = client.get(f"/pdf/{pdf_id}/learning-path", headers=auth_headers)
    assert response.status_code == 504
    detail = response.json()["detail"]
    assert "timed out" in detail.lower()
    assert "test-key" not in detail

    # Confirm no fake roadmap in DB
    path_in_db = db_session.query(LearningPath).filter(LearningPath.pdf_id == pdf_id).first()
    assert path_in_db is None


@pytest.mark.disable_mock_gemini
def test_learning_path_endpoint_repeated_503_returns_promptly(
    client: TestClient, auth_headers, sample_pdf_bytes, monkeypatch, db_session
):
    """
    Verify that repeated 503 UNAVAILABLE errors are bounded by max_retries and return 503.
    """
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("repeated_503.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    mock_client = MagicMock()
    err_503 = genai_errors.ServerError(503, {"error": {"code": 503, "message": "High demand", "status": "UNAVAILABLE"}})
    mock_client.models.generate_content.side_effect = err_503
    monkeypatch.setattr(AIService, "get_client", classmethod(lambda cls: mock_client))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_INITIAL_RETRY_DELAY", 0.001)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRY_DELAY", 0.005)
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", 2)

    response = client.get(f"/pdf/{pdf_id}/learning-path", headers=auth_headers)
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"].lower()
    # 1 initial + 2 retries = 3 calls
    assert mock_client.models.generate_content.call_count == 3
    # No fabricated content
    assert db_session.query(LearningPath).filter(LearningPath.pdf_id == pdf_id).first() is None


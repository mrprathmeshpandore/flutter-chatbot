import pytest
from fastapi.testclient import TestClient


def test_generate_and_get_learning_path(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test generating a structured learning path from a PDF."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("neural_nets.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    # Request learning path
    response = client.get(f"/pdf/{pdf_id}/learning-path", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["pdf_id"] == pdf_id
    assert "topics" in data
    assert len(data["topics"]) >= 1
    assert data["topics"][0]["title"] == "Introduction to Neural Networks"
    assert data["estimated_hours"] > 0


def test_learning_path_persistence(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test that generated learning path is persisted and returned on subsequent calls."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("cached_path.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    # First call generates
    res1 = client.get(f"/pdf/{pdf_id}/learning-path", headers=auth_headers)
    # Second call retrieves cached
    res2 = client.get(f"/pdf/{pdf_id}/learning-path", headers=auth_headers)

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["id"] == res2.json()["id"]


def test_explain_topic_grounded(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test generating an explanation for a topic in the PDF."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("textbook.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    response = client.post(
        f"/pdf/{pdf_id}/explain",
        headers=auth_headers,
        json={"topic": "Neural Networks", "depth": "beginner"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["topic"] == "Neural Networks"
    assert data["depth"] == "beginner"
    assert len(data["explanation"]) > 20


def test_learning_path_unauthorized(client: TestClient, auth_headers, second_auth_headers, sample_pdf_bytes):
    """Test access restriction on another student's learning path."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("secret_course.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    response = client.get(f"/pdf/{pdf_id}/learning-path", headers=second_auth_headers)
    assert response.status_code == 403


def test_learning_path_does_not_fabricate_on_gemini_503(
    client: TestClient, auth_headers, sample_pdf_bytes, monkeypatch, db_session
):
    """Test that when Gemini fails with 503, learning-path returns 503 and does not fabricate dummy modules."""
    from app.services.ai_service import AIService, AIServiceUnavailableError
    from app.models import LearningPath

    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("fail_doc.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    def failing_generate_text(prompt: str, system_instruction: str = None) -> str:
        raise AIServiceUnavailableError(
            message="The AI service is temporarily unavailable due to high demand. Please try again later.",
            status_code=503,
        )

    monkeypatch.setattr(AIService, "generate_text", failing_generate_text)

    response = client.get(f"/pdf/{pdf_id}/learning-path", headers=auth_headers)
    assert response.status_code == 503
    assert "temporarily unavailable" in response.json()["detail"].lower()

    # Verify no fake roadmap is saved in the database
    db_path = db_session.query(LearningPath).filter(LearningPath.pdf_id == pdf_id).first()
    assert db_path is None

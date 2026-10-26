import pytest
from fastapi.testclient import TestClient


def test_ask_ai_general(client: TestClient, auth_headers):
    """Test asking the AI teacher a general question without PDF context."""
    response = client.post(
        "/ai/ask",
        headers=auth_headers,
        json={"question": "What is Python list comprehension?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert data["used_pdf"] is False
    assert data["pdf_id"] is None
    assert data["source_pages"] == []


def test_ask_ai_with_pdf_grounding(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test asking the AI teacher a question grounded in an uploaded PDF."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("ml_guide.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    response = client.post(
        "/ai/ask",
        headers=auth_headers,
        json={
            "question": "How do neural networks learn representations?",
            "pdf_id": pdf_id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["used_pdf"] is True
    assert data["pdf_id"] == pdf_id
    assert 1 in data["source_pages"]
    assert len(data["answer"]) > 10


def test_ask_ai_non_existent_pdf(client: TestClient, auth_headers):
    """Test error handling when asking with an invalid PDF ID."""
    response = client.post(
        "/ai/ask",
        headers=auth_headers,
        json={
            "question": "Explain this document",
            "pdf_id": 99999,
        },
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_ask_ai_unauthorized_pdf(client: TestClient, auth_headers, second_auth_headers, sample_pdf_bytes):
    """Test that student cannot query another student's PDF."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("confidential.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    # Second user attempts to query first user's PDF
    response = client.post(
        "/ai/ask",
        headers=second_auth_headers,
        json={
            "question": "What is in this document?",
            "pdf_id": pdf_id,
        },
    )
    assert response.status_code == 403

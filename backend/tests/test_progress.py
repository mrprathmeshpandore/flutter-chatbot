import pytest
from fastapi.testclient import TestClient


def test_progress_summary(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test getting overall learning progress metrics."""
    # 1. Upload a PDF
    client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("calculus.pdf", sample_pdf_bytes, "application/pdf")},
    )

    # 2. Generate and submit a quiz
    gen_res = client.post(
        "/quiz/generate",
        headers=auth_headers,
        json={"topic": "Calculus", "num_questions": 2},
    )
    quiz_id = gen_res.json()["id"]
    q1_id = gen_res.json()["questions"][0]["id"]
    q2_id = gen_res.json()["questions"][1]["id"]

    client.post(
        "/quiz/submit",
        headers=auth_headers,
        json={
            "quiz_id": quiz_id,
            "answers": [
                {"question_id": q1_id, "selected_option": 0},
                {"question_id": q2_id, "selected_option": 0},
            ],
        },
    )

    # 3. Fetch progress summary
    response = client.get("/progress/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_pdfs"] >= 1
    assert data["total_quizzes_taken"] >= 1
    assert data["average_quiz_score"] == 100.0
    assert len(data["recent_activity"]) >= 2


def test_subject_progress_breakdown(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test breakdown of progress by subject."""
    # 1. Upload a PDF for biology
    client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("biology_textbook.pdf", sample_pdf_bytes, "application/pdf")},
    )

    # 2. Fetch subject breakdown
    response = client.get("/progress/subjects", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "subjects" in data
    assert len(data["subjects"]) >= 1
    subject_names = [s["subject"] for s in data["subjects"]]
    assert any("Biology Textbook" in s for s in subject_names)

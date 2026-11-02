import io
import pytest
from fastapi.testclient import TestClient
from app.models import PDFDocument, PDFPage, LearningPath, Quiz, ProgressLog


def test_complete_end_to_end_flow(client: TestClient, sample_pdf_bytes, monkeypatch):
    """
    Executes and verifies the complete 10-step end-to-end application flow:
    1. Register and Login.
    2. Open Dashboard (Initial Progress).
    3. Upload a PDF.
    4. View Uploaded PDF in Library and File Stream.
    5. Open AI Teacher.
    6. Ask Questions Using PDF Context (RAG with Source Citations).
    7. Generate and Access Learning Path & Topic Explanation.
    8. Generate and Attempt Quiz.
    9. Verify Results and Progress Tracking.
    10. Delete PDF and Verify Related Data Handling & Isolation.
    """

    # ----------------------------------------------------
    # Step 1: Register and Login
    # ----------------------------------------------------
    reg_response = client.post(
        "/auth/register",
        json={
            "email": "student_e2e@mindvault.ai",
            "full_name": "E2E Student",
            "password": "Password123!",
        },
    )
    assert reg_response.status_code == 201
    token_data = reg_response.json()
    assert "access_token" in token_data
    token = token_data["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Verify login
    login_response = client.post(
        "/auth/login",
        json={
            "email": "student_e2e@mindvault.ai",
            "password": "Password123!",
        },
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()
    token = login_response.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Verify /auth/me
    me_response = client.get("/auth/me", headers=auth_headers)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "student_e2e@mindvault.ai"

    # ----------------------------------------------------
    # Step 2: Open Dashboard (Initial Progress)
    # ----------------------------------------------------
    progress_initial = client.get("/progress/summary", headers=auth_headers)
    assert progress_initial.status_code == 200
    summary_data = progress_initial.json()
    assert summary_data["total_pdfs"] == 0
    assert summary_data["total_quizzes_taken"] == 0
    assert summary_data["learning_paths_count"] == 0

    # ----------------------------------------------------
    # Step 3: Upload a PDF
    # ----------------------------------------------------
    pdf_upload_response = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("biology_cell_structure.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert pdf_upload_response.status_code == 201
    uploaded_pdf = pdf_upload_response.json()
    assert uploaded_pdf["id"] is not None
    pdf_id = uploaded_pdf["id"]
    assert uploaded_pdf["page_count"] >= 1
    assert "biology" in uploaded_pdf["filename"].lower()

    # ----------------------------------------------------
    # Step 4: View the Uploaded PDF in Library and Stream
    # ----------------------------------------------------
    library_response = client.get("/pdf/", headers=auth_headers)
    assert library_response.status_code == 200
    pdfs = library_response.json()
    assert len(pdfs) == 1
    assert pdfs[0]["id"] == pdf_id

    # View details
    detail_response = client.get(f"/pdf/{pdf_id}", headers=auth_headers)
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == pdf_id
    assert len(detail["pages"]) >= 1

    # View original PDF file
    file_response = client.get(f"/pdf/{pdf_id}/file", headers=auth_headers)
    assert file_response.status_code == 200
    assert file_response.headers["content-type"] == "application/pdf"
    assert file_response.content.startswith(b"%PDF-")

    # ----------------------------------------------------
    # Step 5 & 6: AI Teacher & Grounded Questions with PDF Context
    # ----------------------------------------------------
    # Ask question using the PDF
    ai_response = client.post(
        "/ai/ask",
        headers=auth_headers,
        json={
            "question": "What is the cell membrane and mitochondria based on this textbook?",
            "pdf_id": pdf_id,
            "history": [],
        },
    )
    assert ai_response.status_code == 200
    ai_data = ai_response.json()
    assert ai_data["used_pdf"] is True
    assert ai_data["pdf_id"] == pdf_id
    assert len(ai_data["answer"]) > 10

    # Ask general question without PDF
    ai_general = client.post(
        "/ai/ask",
        headers=auth_headers,
        json={
            "question": "What is gravity?",
            "history": [],
        },
    )
    assert ai_general.status_code == 200
    assert ai_general.json()["used_pdf"] is False

    # ----------------------------------------------------
    # Step 7: Generate and Access Learning Path & Topic Explanation
    # ----------------------------------------------------
    path_response = client.get(f"/pdf/{pdf_id}/learning-path", headers=auth_headers)
    assert path_response.status_code == 200
    path_data = path_response.json()
    assert path_data["pdf_id"] == pdf_id
    assert "topics" in path_data
    assert len(path_data["topics"]) >= 1

    # Topic explanation
    first_topic = path_data["topics"][0]["title"]
    explain_response = client.post(
        f"/pdf/{pdf_id}/explain",
        headers=auth_headers,
        json={
            "topic": first_topic,
            "depth": "beginner",
        },
    )
    assert explain_response.status_code == 200
    explanation = explain_response.json()
    assert explanation["topic"] == first_topic
    assert len(explanation["explanation"]) > 10

    # ----------------------------------------------------
    # Step 8: Generate and Attempt Quiz
    # ----------------------------------------------------
    quiz_gen_response = client.post(
        "/quiz/generate",
        headers=auth_headers,
        json={
            "pdf_id": pdf_id,
            "num_questions": 5,
            "difficulty": "medium",
        },
    )
    assert quiz_gen_response.status_code == 201
    quiz_data = quiz_gen_response.json()
    assert quiz_data["id"] is not None
    quiz_id = quiz_data["id"]
    assert len(quiz_data["questions"]) == 5

    # Submit quiz answers
    submitted_answers = [
        {"question_id": q["id"], "selected_option": 0}
        for q in quiz_data["questions"]
    ]
    submit_response = client.post(
        "/quiz/submit",
        headers=auth_headers,
        json={
            "quiz_id": quiz_id,
            "answers": submitted_answers,
        },
    )
    assert submit_response.status_code == 200
    result_data = submit_response.json()
    assert result_data["quiz_id"] == quiz_id
    assert result_data["total_questions"] == 5
    assert 0 <= result_data["percentage"] <= 100
    assert len(result_data["details"]) == 5

    # ----------------------------------------------------
    # Step 9: Verify Results and Progress Tracking
    # ----------------------------------------------------
    # Quiz history
    history_response = client.get(f"/quiz/{quiz_id}/results", headers=auth_headers)
    assert history_response.status_code == 200
    assert len(history_response.json()) >= 1

    # Updated Progress Summary
    progress_updated = client.get("/progress/summary", headers=auth_headers)
    assert progress_updated.status_code == 200
    up_summary = progress_updated.json()
    assert up_summary["total_pdfs"] == 1
    assert up_summary["total_quizzes_taken"] == 1
    assert up_summary["learning_paths_count"] == 1
    assert len(up_summary["recent_activity"]) >= 3  # pdf upload, ai question, quiz completed

    # Subject Progress
    subjects_response = client.get("/progress/subjects", headers=auth_headers)
    assert subjects_response.status_code == 200
    assert len(subjects_response.json()["subjects"]) >= 1

    # ----------------------------------------------------
    # Step 10: Delete PDF and Verify Related Data Handling & Isolation
    # ----------------------------------------------------
    # User isolation: another user cannot access this PDF
    reg2_response = client.post(
        "/auth/register",
        json={
            "email": "other_student@mindvault.ai",
            "full_name": "Other Student",
            "password": "Password123!",
        },
    )
    other_headers = {"Authorization": f"Bearer {reg2_response.json()['access_token']}"}
    forbidden_get = client.get(f"/pdf/{pdf_id}", headers=other_headers)
    assert forbidden_get.status_code == 403

    forbidden_delete = client.delete(f"/pdf/{pdf_id}", headers=other_headers)
    assert forbidden_delete.status_code == 403

    # Owner deletes PDF
    delete_response = client.delete(f"/pdf/{pdf_id}", headers=auth_headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["pdf_id"] == pdf_id

    # Verify PDF no longer exists
    get_deleted = client.get(f"/pdf/{pdf_id}", headers=auth_headers)
    assert get_deleted.status_code == 404

    # Verify library is now empty
    list_after = client.get("/pdf/", headers=auth_headers)
    assert len(list_after.json()) == 0

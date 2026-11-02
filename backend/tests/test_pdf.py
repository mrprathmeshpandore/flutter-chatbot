import pytest
from fastapi.testclient import TestClient
from app.config import settings


def test_upload_valid_pdf(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test uploading a valid PDF document with text extraction."""
    response = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("textbook_ml.pdf", sample_pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == "textbook_ml.pdf"
    assert data["page_count"] >= 1
    assert data["file_size"] > 0
    assert "id" in data


def test_upload_non_pdf_extension(client: TestClient, auth_headers):
    """Test rejection of non-PDF file extension."""
    response = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("notes.txt", b"Plain text notes", "text/plain")},
    )
    assert response.status_code == 400
    assert "only pdf files" in response.json()["detail"].lower()


def test_upload_invalid_magic_bytes(client: TestClient, auth_headers):
    """Test rejection of a file named .pdf that lacks PDF magic bytes."""
    response = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("fake.pdf", b"NOT_A_REAL_PDF_STREAM", "application/pdf")},
    )
    assert response.status_code == 400
    assert "valid pdf" in response.json()["detail"].lower()


def test_upload_empty_file(client: TestClient, auth_headers):
    """Test rejection of empty uploaded file."""
    response = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_exceeds_size_limit(client: TestClient, auth_headers, monkeypatch):
    """Test rejection when file exceeds configured MAX_FILE_SIZE_MB."""
    # Temporarily set max size to 1 MB for testing
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_MB", 1)
    
    # 2 MB synthetic content starting with %PDF-
    large_content = b"%PDF-1.4\n" + (b"0" * (2 * 1024 * 1024))
    response = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("large_book.pdf", large_content, "application/pdf")},
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"].lower()


def test_list_pdfs(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test listing all uploaded PDFs for the current user."""
    # Upload two documents
    client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("doc1.pdf", sample_pdf_bytes, "application/pdf")},
    )
    client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("doc2.pdf", sample_pdf_bytes, "application/pdf")},
    )

    response = client.get("/pdf/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_get_pdf_detail(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test retrieving details and pages of an uploaded PDF."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("deep_learning.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    response = client.get(f"/pdf/{pdf_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == pdf_id
    assert len(data["pages"]) >= 1
    assert "Neural networks" in data["pages"][0]["text_content"]


def test_get_pdf_unauthorized_user(client: TestClient, auth_headers, second_auth_headers, sample_pdf_bytes):
    """Test that another student cannot access a private PDF."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("private_notes.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    # Second user tries to access first user's PDF
    response = client.get(f"/pdf/{pdf_id}", headers=second_auth_headers)
    assert response.status_code == 403
    assert "permission" in response.json()["detail"].lower()


def test_delete_pdf(client: TestClient, auth_headers, sample_pdf_bytes, db_session):
    """Test deleting an uploaded PDF document and cascading related data."""
    from app.models import ProgressLog, Quiz

    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("to_delete.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    # Verify progress log was created with pdf_id
    logs_before = db_session.query(ProgressLog).filter(ProgressLog.pdf_id == pdf_id).all()
    assert len(logs_before) >= 1

    delete_res = client.delete(f"/pdf/{pdf_id}", headers=auth_headers)
    assert delete_res.status_code == 200
    assert delete_res.json()["pdf_id"] == pdf_id

    # Verify document no longer exists
    get_res = client.get(f"/pdf/{pdf_id}", headers=auth_headers)
    assert get_res.status_code == 404

    # Verify progress logs for this PDF were cascade-deleted
    logs_after = db_session.query(ProgressLog).filter(ProgressLog.pdf_id == pdf_id).all()
    assert len(logs_after) == 0

    # Verify recent activity on dashboard omits the deleted PDF
    summary_res = client.get("/progress/summary", headers=auth_headers)
    assert summary_res.status_code == 200
    recent = summary_res.json().get("recent_activity", [])
    for activity in recent:
        assert "to_delete" not in activity["subject"].lower()


def test_upload_pdf_with_no_extractable_text(client: TestClient, auth_headers):
    """Test that a valid PDF structure with 0 extractable characters is properly rejected."""
    empty_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        b"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
        b"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]>> endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer <</Size 4 /Root 1 0 R>>\nstartxref\n195\n%%EOF\n"
    )
    response = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("scanned_blank.pdf", empty_pdf, "application/pdf")},
    )
    assert response.status_code == 400
    assert "no extractable text" in response.json()["detail"].lower()

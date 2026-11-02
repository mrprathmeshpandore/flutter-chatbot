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


def test_ask_ai_stream_general(client: TestClient, auth_headers):
    """Test real-time streaming endpoint /ai/ask-stream without PDF context."""
    import json
    response = client.post(
        "/ai/ask-stream",
        headers=auth_headers,
        json={"question": "What is reinforcement learning?"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = []
    for line in response.text.split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    assert len(events) >= 3  # metadata, token(s), done
    assert events[0]["type"] == "metadata"
    assert events[0]["used_pdf"] is False

    tokens = [e["text"] for e in events if e.get("type") == "token"]
    assert len(tokens) >= 1
    streamed_text = "".join(tokens)
    assert len(streamed_text) > 10

    done_event = events[-1]
    assert done_event["type"] == "done"
    assert done_event["used_pdf"] is False


def test_ask_ai_stream_with_pdf(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test real-time streaming endpoint /ai/ask-stream grounded in an uploaded PDF."""
    import json
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("stream_doc.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    response = client.post(
        "/ai/ask-stream",
        headers=auth_headers,
        json={
            "question": "How do neural networks learn representations?",
            "pdf_id": pdf_id,
        },
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = []
    for line in response.text.split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    assert events[0]["type"] == "metadata"
    assert events[0]["used_pdf"] is True
    assert events[0]["pdf_id"] == pdf_id

    tokens = [e["text"] for e in events if e.get("type") == "token"]
    assert len(tokens) >= 1

    done_event = events[-1]
    assert done_event["type"] == "done"
    assert 1 in done_event["source_pages"]
    assert done_event["used_pdf"] is True


def test_ask_ai_stream_non_existent_pdf(client: TestClient, auth_headers):
    """Test streaming error response when requesting a non-existent PDF."""
    response = client.post(
        "/ai/ask-stream",
        headers=auth_headers,
        json={"question": "Summarize", "pdf_id": 99999},
    )
    assert response.status_code == 404


def test_ask_ai_stream_unauthorized_pdf(client: TestClient, auth_headers, second_auth_headers, sample_pdf_bytes):
    """Test streaming authorization check when accessing another user's PDF."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("secret.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    response = client.post(
        "/ai/ask-stream",
        headers=second_auth_headers,
        json={"question": "Tell me secrets", "pdf_id": pdf_id},
    )
    assert response.status_code == 403


def test_ask_ai_question_not_present_in_pdf(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test that asking a question whose answer is not in the PDF returns a clear not-found message."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("ml_guide.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    # Ask about a topic completely absent from the ML guide (e.g. Australian Geography)
    response = client.post(
        "/ai/ask",
        headers=auth_headers,
        json={
            "question": "What is the capital city of Australia and what is its climate?",
            "pdf_id": pdf_id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "could not find this information in your uploaded document" in data["answer"].lower()
    assert data["source_pages"] == []
    assert data["used_pdf"] is True


def test_ask_ai_stream_question_not_present_in_pdf(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test streaming response when question is not present in the uploaded document."""
    import json
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("ml_guide.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    response = client.post(
        "/ai/ask-stream",
        headers=auth_headers,
        json={
            "question": "What is the recipe for baking chocolate cake?",
            "pdf_id": pdf_id,
        },
    )
    assert response.status_code == 200

    events = []
    for line in response.text.split("\n"):
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))

    done_event = events[-1]
    assert done_event["type"] == "done"
    assert "could not find this information in your uploaded document" in done_event["full_answer"].lower()
    assert done_event["source_pages"] == []


def test_ask_ai_multiple_pdfs_correct_selection(client: TestClient, auth_headers):
    """Test that when a user uploads multiple PDFs, questions are answered strictly from the selected PDF."""
    pdf1_content = b"""%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /Resources <</Font <</F1 4 0 R>>>> /MediaBox [0 0 612 792] /Contents 5 0 R>> endobj
4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj
5 0 obj <</Length 120>> stream
BT
/F1 14 Tf
70 700 Td
(Machine Learning Fundamentals. Neural networks learn representations from data.) Tj
ET
endstream endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000229 00000 n 
0000000300 00000 n 
trailer <</Size 6 /Root 1 0 R>>
startxref
470
%%EOF
"""
    pdf2_content = b"""%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /Resources <</Font <</F1 4 0 R>>>> /MediaBox [0 0 612 792] /Contents 5 0 R>> endobj
4 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj
5 0 obj <</Length 130>> stream
BT
/F1 14 Tf
70 700 Td
(Ancient Egypt. The Great Pyramids were monumental tombs built with limestone blocks.) Tj
ET
endstream endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000229 00000 n 
0000000300 00000 n 
trailer <</Size 6 /Root 1 0 R>>
startxref
480
%%EOF
"""
    # 1. Upload both documents
    res1 = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("doc_ml.pdf", pdf1_content, "application/pdf")},
    )
    pdf1_id = res1.json()["id"]

    res2 = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("doc_egypt.pdf", pdf2_content, "application/pdf")},
    )
    pdf2_id = res2.json()["id"]

    # 2. Query PDF 2 for pyramids topic
    res_egypt = client.post(
        "/ai/ask",
        headers=auth_headers,
        json={"question": "How were the Great Pyramids built?", "pdf_id": pdf2_id},
    )
    assert res_egypt.status_code == 200
    data_egypt = res_egypt.json()
    assert 1 in data_egypt["source_pages"]
    assert data_egypt["pdf_id"] == pdf2_id

    # 3. Query PDF 1 for pyramids topic -> should NOT find it in PDF 1
    res_mismatch = client.post(
        "/ai/ask",
        headers=auth_headers,
        json={"question": "How were the Great Pyramids built?", "pdf_id": pdf1_id},
    )
    assert res_mismatch.status_code == 200
    data_mismatch = res_mismatch.json()
    assert "could not find this information in your uploaded document" in data_mismatch["answer"].lower()
    assert data_mismatch["source_pages"] == []

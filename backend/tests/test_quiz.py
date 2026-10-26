import pytest
from fastapi.testclient import TestClient


def test_generate_quiz_from_topic(client: TestClient, auth_headers):
    """Test generating a quiz for a general study topic."""
    response = client.post(
        "/quiz/generate",
        headers=auth_headers,
        json={
            "topic": "Neural Networks",
            "num_questions": 2,
            "difficulty": "medium",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert len(data["questions"]) == 2
    for q in data["questions"]:
        assert len(q["options"]) == 4
        # Verify correct_option is NOT exposed during quiz taking
        assert "correct_option" not in q


def test_generate_quiz_from_pdf(client: TestClient, auth_headers, sample_pdf_bytes):
    """Test generating a quiz based on an uploaded textbook PDF."""
    upload_res = client.post(
        "/pdf/upload",
        headers=auth_headers,
        files={"file": ("deep_learning.pdf", sample_pdf_bytes, "application/pdf")},
    )
    pdf_id = upload_res.json()["id"]

    response = client.post(
        "/quiz/generate",
        headers=auth_headers,
        json={
            "pdf_id": pdf_id,
            "num_questions": 2,
            "difficulty": "hard",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["pdf_id"] == pdf_id
    assert len(data["questions"]) == 2


def test_submit_quiz_scoring(client: TestClient, auth_headers):
    """Test quiz submission and accurate score calculation."""
    # 1. Generate quiz with 2 questions (correct options in mock are both 0)
    gen_res = client.post(
        "/quiz/generate",
        headers=auth_headers,
        json={"topic": "Neural Networks", "num_questions": 2},
    )
    quiz_id = gen_res.json()["id"]
    q1_id = gen_res.json()["questions"][0]["id"]
    q2_id = gen_res.json()["questions"][1]["id"]

    # 2. Submit: Q1 correct (0), Q2 incorrect (1)
    sub_res = client.post(
        "/quiz/submit",
        headers=auth_headers,
        json={
            "quiz_id": quiz_id,
            "answers": [
                {"question_id": q1_id, "selected_option": 0},
                {"question_id": q2_id, "selected_option": 1},
            ],
        },
    )
    assert sub_res.status_code == 200
    res_data = sub_res.json()
    assert res_data["total_questions"] == 2
    assert res_data["correct_answers"] == 1
    assert res_data["percentage"] == 50.0
    assert len(res_data["details"]) == 2
    assert res_data["details"][0]["is_correct"] is True
    assert res_data["details"][1]["is_correct"] is False


def test_submit_quiz_perfect_score(client: TestClient, auth_headers):
    """Test submitting 100% correct answers."""
    gen_res = client.post(
        "/quiz/generate",
        headers=auth_headers,
        json={"topic": "Deep Learning", "num_questions": 2},
    )
    quiz_id = gen_res.json()["id"]
    q1_id = gen_res.json()["questions"][0]["id"]
    q2_id = gen_res.json()["questions"][1]["id"]

    sub_res = client.post(
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
    assert sub_res.status_code == 200
    assert sub_res.json()["percentage"] == 100.0
    assert sub_res.json()["correct_answers"] == 2


def test_get_quiz_results_history(client: TestClient, auth_headers):
    """Test retrieving history of past quiz results."""
    gen_res = client.post(
        "/quiz/generate",
        headers=auth_headers,
        json={"topic": "Math Fundamentals", "num_questions": 2},
    )
    quiz_id = gen_res.json()["id"]
    q1_id = gen_res.json()["questions"][0]["id"]
    q2_id = gen_res.json()["questions"][1]["id"]

    # Submit twice
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
    client.post(
        "/quiz/submit",
        headers=auth_headers,
        json={
            "quiz_id": quiz_id,
            "answers": [
                {"question_id": q1_id, "selected_option": 0},
                {"question_id": q2_id, "selected_option": 1},
            ],
        },
    )

    history_res = client.get(f"/quiz/{quiz_id}/results", headers=auth_headers)
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert len(history_data) == 2
    assert history_data[0]["percentage"] in [50.0, 100.0]


def test_quiz_unauthorized_submit(client: TestClient, auth_headers, second_auth_headers):
    """Test that a student cannot submit answers to another student's quiz."""
    gen_res = client.post(
        "/quiz/generate",
        headers=auth_headers,
        json={"topic": "Private Quiz", "num_questions": 2},
    )
    quiz_id = gen_res.json()["id"]

    # Second student tries to submit
    sub_res = client.post(
        "/quiz/submit",
        headers=second_auth_headers,
        json={"quiz_id": quiz_id, "answers": []},
    )
    assert sub_res.status_code == 403

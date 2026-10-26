import pytest
from fastapi.testclient import TestClient


def test_register_success(client: TestClient):
    """Test creating a new student account successfully."""
    response = client.post(
        "/auth/register",
        json={
            "email": "newstudent@mindvault.ai",
            "password": "securepassword123",
            "full_name": "Jordan Smith",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "newstudent@mindvault.ai"
    assert data["user"]["full_name"] == "Jordan Smith"
    assert "password" not in data["user"]
    assert "hashed_password" not in data["user"]


def test_register_duplicate_email(client: TestClient, test_user):
    """Test duplicate registration error."""
    response = client.post(
        "/auth/register",
        json={
            "email": test_user.email,
            "password": "anotherpassword",
            "full_name": "Duplicate Student",
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_register_short_password(client: TestClient):
    """Test validation rejection for password shorter than 6 characters."""
    response = client.post(
        "/auth/register",
        json={
            "email": "shortpw@mindvault.ai",
            "password": "123",
            "full_name": "Short PW",
        },
    )
    assert response.status_code == 422


def test_login_success(client: TestClient, test_user):
    """Test logging in with correct credentials."""
    response = client.post(
        "/auth/login",
        json={
            "email": test_user.email,
            "password": "password123",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == test_user.email


def test_login_wrong_password(client: TestClient, test_user):
    """Test login rejection for wrong password."""
    response = client.post(
        "/auth/login",
        json={
            "email": test_user.email,
            "password": "wrongpassword!",
        },
    )
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


def test_login_unknown_email(client: TestClient):
    """Test login rejection for non-existent email."""
    response = client.post(
        "/auth/login",
        json={
            "email": "ghost@mindvault.ai",
            "password": "somepassword123",
        },
    )
    assert response.status_code == 401


def test_get_me_success(client: TestClient, auth_headers, test_user):
    """Test accessing current user profile with valid Bearer token."""
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == test_user.email
    assert data["id"] == test_user.id


def test_get_me_unauthorized(client: TestClient):
    """Test accessing /auth/me without Bearer token returns 401."""
    response = client.get("/auth/me")
    assert response.status_code == 401

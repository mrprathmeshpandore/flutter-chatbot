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


def test_update_me_success(client: TestClient, auth_headers, test_user):
    """Test updating user profile full name, email, and phone number."""
    response = client.put(
        "/auth/me",
        headers=auth_headers,
        json={
            "full_name": "Prathamesh Updated",
            "phone_number": "+1234567890",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Prathamesh Updated"
    assert data["phone_number"] == "+1234567890"


def test_update_me_duplicate_email(client: TestClient, auth_headers, test_user):
    """Test updating to an already taken email returns 400."""
    # Register another user first
    reg = client.post(
        "/auth/register",
        json={
            "email": "otheruser@mindvault.ai",
            "password": "password123",
            "full_name": "Other User",
        },
    )
    assert reg.status_code == 201

    # Try to change test_user email to otheruser@mindvault.ai
    response = client.put(
        "/auth/me",
        headers=auth_headers,
        json={"email": "otheruser@mindvault.ai"},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_avatar_lifecycle(client: TestClient, auth_headers, test_user):
    """Test uploading, serving, and deleting user profile avatar."""
    # Valid PNG image bytes (1x1 transparent PNG)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    # 1. Upload avatar
    response = client.post(
        "/auth/me/avatar",
        headers=auth_headers,
        files={"file": ("avatar.png", png_bytes, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["profile_image"] is not None
    avatar_url = data["profile_image"]
    assert avatar_url.startswith("/auth/avatar/")

    # 2. Fetch avatar image
    avatar_res = client.get(avatar_url)
    assert avatar_res.status_code == 200
    assert avatar_res.content == png_bytes

    # 3. Delete avatar
    del_res = client.delete("/auth/me/avatar", headers=auth_headers)
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["profile_image"] is None

    # 4. Fetch deleted avatar returns 404
    avatar_404 = client.get(avatar_url)
    assert avatar_404.status_code == 404


def test_avatar_invalid_format(client: TestClient, auth_headers):
    """Test that non-image or fake-extension files are rejected."""
    fake_bytes = b"not a real image"
    response = client.post(
        "/auth/me/avatar",
        headers=auth_headers,
        files={"file": ("fake.png", fake_bytes, "image/png")},
    )
    assert response.status_code == 400
    assert "does not match" in response.json()["detail"].lower()


def test_avatar_jpg_upload(client: TestClient, auth_headers):
    """Test uploading a valid JPG image."""
    jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x01\xff\xd9"
    response = client.post(
        "/auth/me/avatar",
        headers=auth_headers,
        files={"file": ("profile.jpg", jpg_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["profile_image"] is not None
    assert data["profile_image"].endswith(".jpg")


def test_avatar_jpeg_upload(client: TestClient, auth_headers):
    """Test uploading a valid JPEG image."""
    jpeg_bytes = b"\xff\xd8\xff\xe1\x00\x18Exif\x00\x00II*\x00\x08\x00\x00\x00\x00\x00\x00\x00\xff\xd9"
    response = client.post(
        "/auth/me/avatar",
        headers=auth_headers,
        files={"file": ("photo.jpeg", jpeg_bytes, "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["profile_image"] is not None
    assert data["profile_image"].endswith(".jpeg")


def test_avatar_webp_upload(client: TestClient, auth_headers):
    """Test uploading a valid WEBP image."""
    webp_bytes = b"RIFF\x18\x00\x00\x00WEBPVP8 \x0c\x00\x00\x000\x01\x00\x9d\x01*\x01\x00\x01\x00\x00\x00"
    response = client.post(
        "/auth/me/avatar",
        headers=auth_headers,
        files={"file": ("avatar.webp", webp_bytes, "image/webp")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["profile_image"] is not None
    assert data["profile_image"].endswith(".webp")


def test_avatar_android_octet_stream_upload(client: TestClient, auth_headers):
    """Test uploading an image when Android sends application/octet-stream MIME type."""
    jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    response = client.post(
        "/auth/me/avatar",
        headers=auth_headers,
        files={"file": ("1000000001.jpg", jpg_bytes, "application/octet-stream")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["profile_image"] is not None
    assert data["profile_image"].startswith("/auth/avatar/")


def test_avatar_disallowed_mime_type(client: TestClient, auth_headers):
    """Test that non-image MIME types like application/pdf or text/html are rejected."""
    pdf_bytes = b"%PDF-1.4 sample content"
    response = client.post(
        "/auth/me/avatar",
        headers=auth_headers,
        files={"file": ("document.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 400
    assert "invalid mime type" in response.json()["detail"].lower()


def test_avatar_mismatched_extension(client: TestClient, auth_headers):
    """Test that claiming to be .png while bytes are JPEG is rejected."""
    jpg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
    response = client.post(
        "/auth/me/avatar",
        headers=auth_headers,
        files={"file": ("fake_png.png", jpg_bytes, "image/png")},
    )
    assert response.status_code == 400



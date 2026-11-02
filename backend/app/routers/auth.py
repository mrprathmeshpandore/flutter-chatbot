import os
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import UserRegister, UserLogin, UserOut, UserUpdate, Token
from app.services.auth_service import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

ALLOWED_AVATAR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_AVATAR_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/jpg",
    "image/pjpeg",
    "image/x-png",
    "application/octet-stream",
}
MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def detect_image_format_from_magic_bytes(content: bytes) -> tuple[str | None, str | None]:
    """
    Safely determines the actual image type and canonical extension from binary magic bytes.
    Validates:
      - JPEG: FF D8 FF
      - PNG:  89 50 4E 47 (\x89PNG)
      - WEBP: RIFF....WEBP (offset 0: 'RIFF', offset 8..12: 'WEBP')
    Returns (detected_mime, canonical_ext) or (None, None).
    """
    if len(content) < 3:
        return None, None

    # JPEG: starts with FF D8 FF
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"

    # PNG: starts with 89 50 4E 47 (\x89PNG)
    if content.startswith(b"\x89PNG") or content.startswith(b"\x89\x50\x4e\x47"):
        return "image/png", ".png"

    # WEBP: RIFF header with WEBP identifier at offset 8..12
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp", ".webp"

    return None, None


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account",
)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    """
    Creates a new user account with hashed password and returns an access token.
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_in.email.lower().strip()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # Hash password and create user
    hashed_pwd = get_password_hash(user_in.password)
    new_user = User(
        email=user_in.email.lower().strip(),
        full_name=user_in.full_name,
        hashed_password=hashed_pwd,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate JWT access token
    access_token = create_access_token(data={"sub": new_user.email, "user_id": new_user.id})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(new_user),
    )


@router.post(
    "/login",
    response_model=Token,
    summary="Log into an existing account",
)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticates user credentials and returns a signed JWT token.
    """
    user = db.query(User).filter(User.email == credentials.email.lower().strip()).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive.",
        )

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get currently authenticated student profile",
)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Returns the profile information of the currently authenticated user.
    """
    return current_user


@router.put(
    "/me",
    response_model=UserOut,
    summary="Update authenticated user profile information",
)
def update_me(
    user_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Updates the authenticated user's profile information (full_name, email, phone_number).
    Validates email uniqueness and input formats.
    """
    if user_in.email is not None:
        normalized_email = user_in.email.lower().strip()
        if normalized_email != current_user.email:
            existing = db.query(User).filter(User.email == normalized_email, User.id != current_user.id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A user with this email address already exists.",
                )
            current_user.email = normalized_email

    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name.strip()

    if user_in.phone_number is not None:
        current_user.phone_number = user_in.phone_number.strip()

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post(
    "/me/avatar",
    response_model=UserOut,
    summary="Upload or update authenticated user profile avatar photo",
)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Uploads a new profile avatar photo from phone gallery.
    Validates file extension, client MIME type, binary magic bytes, and file size.
    Saves securely in uploads/avatars/ and updates user profile.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided for uploaded avatar.",
        )

    # 1. Validate client-supplied MIME type (reject non-image / dangerous MIME types upfront)
    raw_mime = None
    if file.content_type:
        raw_mime = file.content_type.lower().split(";")[0].strip()
        if raw_mime not in ALLOWED_AVATAR_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid MIME type '{file.content_type}'. Must be a JPEG, PNG, or WEBP image.",
            )

    # 2. Read image content with size limit check
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if len(content) > MAX_AVATAR_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image file size ({len(content) // 1024} KB) exceeds the maximum allowed size of 5 MB.",
        )

    # 3. Inspect binary magic bytes to safely determine the true image format
    detected_mime, canonical_ext = detect_image_format_from_magic_bytes(content)
    if not detected_mime or not canonical_ext:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match a valid image format. Must be a JPEG, PNG, or WEBP image.",
        )

    # 4. Cross-validate client-supplied image MIME type with actual detected format
    if raw_mime and raw_mime != "application/octet-stream":
        if raw_mime in {"image/jpeg", "image/jpg", "image/pjpeg"} and detected_mime != "image/jpeg":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Supplied MIME type '{file.content_type}' does not match actual image content.",
            )
        elif raw_mime in {"image/png", "image/x-png"} and detected_mime != "image/png":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Supplied MIME type '{file.content_type}' does not match actual image content.",
            )
        elif raw_mime == "image/webp" and detected_mime != "image/webp":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Supplied MIME type '{file.content_type}' does not match actual image content.",
            )

    # 5. Check and resolve file extension
    _, raw_ext = os.path.splitext(file.filename.lower())
    if raw_ext in ALLOWED_AVATAR_EXTENSIONS:
        if raw_ext in {".jpg", ".jpeg"} and detected_mime != "image/jpeg":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{raw_ext}' does not match actual {detected_mime} image content.",
            )
        if raw_ext == ".png" and detected_mime != "image/png":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{raw_ext}' does not match actual {detected_mime} image content.",
            )
        if raw_ext == ".webp" and detected_mime != "image/webp":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File extension '{raw_ext}' does not match actual {detected_mime} image content.",
            )
        final_ext = raw_ext
    else:
        # Fallback to canonical extension detected from magic bytes
        final_ext = canonical_ext

    avatar_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)

    # Clean up previous avatar file if exists
    if current_user.profile_image and current_user.profile_image.startswith("/auth/avatar/"):
        old_filename = os.path.basename(current_user.profile_image)
        old_path = os.path.join(avatar_dir, old_filename)
        if os.path.isfile(old_path):
            try:
                os.remove(old_path)
            except Exception as e:
                logger.warning(f"Failed to remove previous avatar file {old_path}: {e}")

    unique_filename = f"user_{current_user.id}_{uuid.uuid4().hex[:10]}{final_ext}"
    dest_path = os.path.join(avatar_dir, unique_filename)

    with open(dest_path, "wb") as f:
        f.write(content)

    current_user.profile_image = f"/auth/avatar/{unique_filename}"
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete(
    "/me/avatar",
    response_model=UserOut,
    summary="Remove authenticated user profile avatar photo",
)
def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Removes the user's profile avatar photo and deletes the file from disk.
    """
    if current_user.profile_image:
        if current_user.profile_image.startswith("/auth/avatar/"):
            old_filename = os.path.basename(current_user.profile_image)
            avatar_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
            old_path = os.path.join(avatar_dir, old_filename)
            if os.path.isfile(old_path):
                try:
                    os.remove(old_path)
                except Exception as e:
                    logger.warning(f"Failed to remove avatar file {old_path}: {e}")

        current_user.profile_image = None
        db.commit()
        db.refresh(current_user)

    return current_user


@router.get(
    "/avatar/{filename}",
    summary="Serve profile avatar image",
)
def get_avatar(filename: str):
    """
    Safely serves an uploaded user profile avatar image.
    """
    safe_filename = os.path.basename(filename)
    avatar_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    file_path = os.path.join(avatar_dir, safe_filename)

    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Avatar image not found.",
        )

    return FileResponse(file_path)


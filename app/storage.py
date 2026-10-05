"""
Supabase Storage helper — upload images to a bucket, get public URLs.
Falls back to local disk storage if STORAGE_BACKEND=local (useful for
development without a real Supabase project yet).
"""
import os
import uuid
import aiofiles
from pathlib import Path
try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None

from app.config import (
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_STORAGE_BUCKET, STORAGE_BACKEND, APP_BASE_URL,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
)

try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    if CLOUDINARY_CLOUD_NAME:
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET
        )
except ImportError:
    cloudinary = None

# Local uploads directory (used when STORAGE_BACKEND=local)
LOCAL_UPLOAD_DIR = Path(__file__).parent.parent / "uploads"


def _get_supabase_client() -> Client:
    if create_client is None:
        raise RuntimeError("supabase package is not installed. Run 'pip install supabase'.")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


async def upload_image(data: bytes, content_type: str, folder: str = "general") -> str:
    """
    Uploads compressed image bytes and returns a public URL string.
    folder: "receipts", "photos", "offers", etc.
    """
    filename = f"{folder}/{uuid.uuid4().hex}.jpg"

    if STORAGE_BACKEND == "cloudinary":
        # Cloudinary expects bytes if we upload via file-like object, or base64. 
        # But we can just pass the bytes directly.
        response = cloudinary.uploader.upload(
            data,
            folder=f"amenco/{folder}",
            resource_type="image"
        )
        return response.get("secure_url")
    elif STORAGE_BACKEND == "supabase":
        sb: Client = _get_supabase_client()
        sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
            path=filename,
            file=data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        public_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(filename)
        return public_url
    else:
        # Local fallback
        LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        folder_path = LOCAL_UPLOAD_DIR / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        file_path = folder_path / f"{uuid.uuid4().hex}.jpg"
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(data)
        # Return a URL relative to the backend server
        rel = str(file_path.relative_to(LOCAL_UPLOAD_DIR.parent)).replace("\\", "/")
        return f"{APP_BASE_URL}/{rel}"

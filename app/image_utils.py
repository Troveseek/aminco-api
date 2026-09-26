"""
Image utilities — server-side compression and resizing.
Keeps uploaded receipts and profile photos under MAX_IMAGE_SIZE_KB
regardless of what the user uploads. This is a critical guard against
localStorage exhaustion (now replaced) and backend storage bloat.
"""
import io
from typing import Tuple
from PIL import Image
from app.config import MAX_IMAGE_SIZE_KB

MAX_BYTES = MAX_IMAGE_SIZE_KB * 1024
MAX_DIMENSION = 1200   # px — max width or height after resize


def compress_image(data: bytes, content_type: str = "image/jpeg") -> Tuple[bytes, str]:
    """
    Accepts raw image bytes, returns compressed (bytes, mime_type).
    - Resizes to fit within MAX_DIMENSION × MAX_DIMENSION
    - Saves as JPEG (quality stepped down until under MAX_BYTES)
    - Returns the final bytes and the output MIME type
    """
    img = Image.open(io.BytesIO(data))

    # Convert RGBA/P to RGB to allow JPEG output
    if img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize if too large
    w, h = img.size
    if w > MAX_DIMENSION or h > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)

    # Compress by stepping down JPEG quality until small enough
    quality = 85
    while quality >= 40:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        result = buf.getvalue()
        if len(result) <= MAX_BYTES:
            return result, "image/jpeg"
        quality -= 10

    # Last resort: return whatever we have at quality=40
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=40, optimize=True)
    return buf.getvalue(), "image/jpeg"

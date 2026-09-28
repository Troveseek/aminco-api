"""
Real QR code generation.
Encodes a public verify URL that any vendor can scan to confirm a student's
active membership in real-time.
"""
import io
import qrcode
from qrcode.image.pil import PilImage
from app.config import APP_BASE_URL


def generate_verify_qr_png(student_id: int) -> bytes:
    """
    Returns a PNG image (as bytes) containing a real, scannable QR code
    that encodes: https://amenco-club.netlify.app/verify.html?id=<student_id>
    """
    verify_url = f"https://amenco-club.netlify.app/verify.html?id={student_id}"

    qr = qrcode.QRCode(
        version=None,          # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)

    img: PilImage = qr.make_image(fill_color="#0097B2", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

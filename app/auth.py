"""
JWT creation/verification + bcrypt password hashing.
Never returns raw passwords. JWT payloads contain only {sub, role, exp}.
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_db
from app import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


# ──────────────────────────────────────────────
# Password hashing
# ──────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ──────────────────────────────────────────────
# JWT creation
# ──────────────────────────────────────────────

def create_access_token(subject: str, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    subject: str(student.id) or str(admin.id)
    role: "student" or "admin"
    """
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="توكن الجلسة غير صالح أو منتهي الصلاحية",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ──────────────────────────────────────────────
# FastAPI dependency helpers
# ──────────────────────────────────────────────

async def get_current_student(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> models.Student:
    if credentials is None:
        raise HTTPException(status_code=401, detail="يرجى تسجيل الدخول أولاً")
    payload = decode_token(credentials.credentials)
    if payload.get("role") != "student":
        raise HTTPException(status_code=403, detail="الصلاحية غير كافية")
    student_id = int(payload["sub"])
    result = await db.execute(select(models.Student).where(models.Student.id == student_id))
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=401, detail="الحساب غير موجود")
    return student


async def get_current_student_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[models.Student]:
    """For endpoints that work for both guests and logged-in users (e.g. offer browsing)."""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("role") != "student":
            return None
        student_id = int(payload["sub"])
        result = await db.execute(select(models.Student).where(models.Student.id == student_id))
        return result.scalar_one_or_none()
    except Exception:
        return None


async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> models.AdminUser:
    if credentials is None:
        raise HTTPException(status_code=401, detail="يرجى تسجيل دخول المشرف أولاً")
    payload = decode_token(credentials.credentials)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="هذا المسار خاص بالمشرفين فقط")
    admin_id = int(payload["sub"])
    result = await db.execute(select(models.AdminUser).where(models.AdminUser.id == admin_id))
    admin = result.scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=401, detail="حساب المشرف غير موجود")
    return admin

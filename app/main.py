"""
AMENCO Club — FastAPI Backend Entrypoint
Registers all routers, configures CORS, and handles startup (DB init + admin seed).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, APP_BASE_URL
from app.database import engine, is_sqlite
from app.models import Base
from app.routers import students, offers, payments, verify, admin, categories

app = FastAPI(
    title="AMENCO Club API",
    description="Backend API for AMENCO Club — Student Privileges & Discounts Platform, Sétif, Algeria",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────
# Allow all origins in demo mode. In production, restrict to your frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(students.router)
app.include_router(offers.router)
app.include_router(payments.router)
app.include_router(verify.router)
app.include_router(verify.router, prefix="/api")
app.include_router(admin.router)
app.include_router(categories.router)

from typing import List, Optional
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import schemas, models

@app.get("/api/settings", response_model=schemas.PublicSettingOut)
async def get_public_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Setting).limit(1))
    s = result.scalar_one_or_none()
    if not s:
        return schemas.PublicSettingOut(
            baridimob_account="0799 12 34 56",
            ccp_account="",
            account_holder="محمد أمين بوكتاشة",
            payment_note="سيتم تفعيل اشتراكك خلال 24 ساعة من التحقق من وصل الدفع",
            subscription_price=2000,
        )
    return schemas.PublicSettingOut.model_validate(s)

@app.get("/api/partners", response_model=List[schemas.PublicPartnerOut])
@app.get("/api/vendors", response_model=List[schemas.PublicPartnerOut])
async def list_public_partners(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(models.Vendor).where(models.Vendor.active == True)
    if category and category != "الكل":
        stmt = stmt.where(models.Vendor.category == category)
    result = await db.execute(stmt.order_by(models.Vendor.name.asc()))
    return result.scalars().all()

# ── Static files (local uploaded images in dev mode) ─────────
uploads_dir = Path(__file__).parent.parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


async def _safe_migrate_column(table_name: str, col_name: str, col_type: str):
    from sqlalchemy import text
    try:
        async with engine.begin() as conn:
            if is_sqlite:
                result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
                existing_cols = [row[1] for row in result.fetchall()]
                if col_name not in existing_cols:
                    await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
            else:
                # PostgreSQL 9.6+ supports ADD COLUMN IF NOT EXISTS
                await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
    except Exception as e:
        print(f"Migration note for {table_name}.{col_name}: {e}", flush=True)


# ── Startup: create tables + ensure admin user exists ─────────
@app.on_event("startup")
async def startup():
    print("[INFO] Application starting up...", flush=True)
    try:
        # Create all tables if they don't exist
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[OK] Database tables verified/created", flush=True)
    except Exception as e:
        print(f"[NOTE] Notice during Base.metadata.create_all: {e}", flush=True)

    # Safe migrations for new columns
    await _safe_migrate_column("vendors", "instagram_url", "VARCHAR(255)")
    await _safe_migrate_column("vendors", "tiktok_url", "VARCHAR(255)")
    await _safe_migrate_column("vendors", "location_url", "TEXT")
    await _safe_migrate_column("vendors", "logo_url", "TEXT")
    await _safe_migrate_column("settings", "ccp_account", "VARCHAR(100)")
    await _safe_migrate_column("referrals", "settled_amount", "INTEGER DEFAULT 0")

    # Ensure the default admin user exists
    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models import AdminUser, Setting, Category, University
    from app.auth import hash_password

    try:
        async with AsyncSessionLocal() as session:
            # 1. Admin
            try:
                result = await session.execute(
                    select(AdminUser).where(AdminUser.email == ADMIN_EMAIL)
                )
                if not result.scalar_one_or_none():
                    session.add(AdminUser(
                        email=ADMIN_EMAIL,
                        password_hash=hash_password(ADMIN_PASSWORD),
                    ))
                    await session.commit()
                    print(f"[OK] Admin user created: {ADMIN_EMAIL}", flush=True)
                else:
                    print(f"[OK] Admin user exists: {ADMIN_EMAIL}", flush=True)
            except Exception as e:
                print(f"[NOTE] Admin seed note: {e}", flush=True)
                await session.rollback()

            # 2. Settings
            try:
                s_result = await session.execute(select(Setting).limit(1))
                if not s_result.scalar_one_or_none():
                    session.add(Setting(
                        baridimob_account="0799 12 34 56",
                        account_holder="محمد أمين بوكتاشة",
                        payment_note="سيتم تفعيل اشتراكك خلال 24 ساعة من التحقق من الدفع",
                        subscription_price=1000,
                        admin_email=ADMIN_EMAIL,
                        app_version="1.0.0",
                    ))
                    await session.commit()
                    print("[OK] Default settings created", flush=True)
            except Exception as e:
                print(f"[NOTE] Settings seed note: {e}", flush=True)
                await session.rollback()

            # 3. Categories
            try:
                cat_result = await session.execute(select(Category).limit(1))
                if not cat_result.scalar_one_or_none():
                    default_cats = [
                        Category(label='مطاعم وكافيهات', icon='restaurant'),
                        Category(label='رياضة', icon='fitness_center'),
                        Category(label='تعليم ومكتبات', icon='menu_book'),
                        Category(label='خدمات', icon='medical_services'),
                        Category(label='ترفيه', icon='local_activity')
                    ]
                    session.add_all(default_cats)
                    await session.commit()
                    print("[OK] Default categories created", flush=True)
            except Exception as e:
                print(f"[NOTE] Categories seed note: {e}", flush=True)
                await session.rollback()

            # 4. Universities
            try:
                uni_result = await session.execute(select(University).limit(1))
                if not uni_result.scalar_one_or_none():
                    default_unis = [
                        University(name="جامعة فرحات عباس - سطيف 1"),
                        University(name="جامعة محمد لمين دباغين - سطيف 2"),
                        University(name="الجامعة المركزية"),
                        University(name="المدرسة العليا للأساتذة")
                    ]
                    session.add_all(default_unis)
                    await session.commit()
                    print("[OK] Default universities created in database", flush=True)
            except Exception as e:
                print(f"[NOTE] Universities seed note: {e}", flush=True)
                await session.rollback()

    except Exception as e:
        print(f"[NOTE] Notice during startup session: {e}", flush=True)

    print("[SUCCESS] Application startup finished successfully!", flush=True)


# ── Health check ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "AMENCO Club API", "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "name": "AMENCO Club API",
        "docs": f"{APP_BASE_URL}/docs",
        "health": f"{APP_BASE_URL}/health",
    }


@app.get("/api/universities")
@app.get("/universities")
async def get_universities():
    from app.database import AsyncSessionLocal
    from app.models import University
    from sqlalchemy import select
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(University).order_by(University.id))
            unis = result.scalars().all()
            if unis:
                return [u.name for u in unis]
    except Exception as e:
        print("Database error in get_universities fallback:", e)
    return [
        "جامعة فرحات عباس - سطيف 1",
        "جامعة محمد لمين دباغين - سطيف 2",
        "الجامعة المركزية",
        "المدرسة العليا للأساتذة"
    ]

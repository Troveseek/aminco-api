"""
AMENCO Club — FastAPI Backend Entrypoint
Registers all routers, configures CORS, and handles startup (DB init + admin seed).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, APP_BASE_URL
from app.database import engine
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
app.include_router(admin.router)
app.include_router(categories.router)

# ── Static files (local uploaded images in dev mode) ─────────
uploads_dir = Path(__file__).parent.parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


# ── Startup: create tables + ensure admin user exists ─────────
@app.on_event("startup")
async def startup():
    # Create all tables if they don't exist
    # NOTE: In production, use Alembic migrations instead of create_all.
    # For local dev and initial Supabase setup, create_all is convenient.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Ensure the default admin user exists
    from app.database import AsyncSessionLocal
    from sqlalchemy import select
    from app.models import AdminUser, Setting
    from app.auth import hash_password
    from datetime import datetime

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AdminUser).where(AdminUser.email == ADMIN_EMAIL)
        )
        if not result.scalar_one_or_none():
            session.add(AdminUser(
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
            ))
            await session.commit()
            print(f"Admin user created: {ADMIN_EMAIL}")
        else:
            print(f"Admin user exists: {ADMIN_EMAIL}")

        # Ensure settings row exists
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
            print("✅ Default settings created")

        # Seed categories
        from app.models import Category
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
            print("✅ Default categories created")


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
async def get_universities():
    return [
        "جامعة فرحات عباس - سطيف 1",
        "جامعة محمد لمين دباغين - سطيف 2",
        "الجامعة المركزية",
        "المدرسة العليا للأساتذة"
    ]

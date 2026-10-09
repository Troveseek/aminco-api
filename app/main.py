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


# ── Startup: create tables + ensure admin user exists ─────────
@app.on_event("startup")
async def startup():
    # Create all tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Safe migration for new vendor columns if table already existed
        for col, col_type in [
            ("instagram_url", "VARCHAR(255)"),
            ("tiktok_url", "VARCHAR(255)"),
            ("location_url", "TEXT"),
            ("logo_url", "TEXT"),
        ]:
            try:
                from sqlalchemy import text
                await conn.execute(text(f"ALTER TABLE vendors ADD COLUMN {col} {col_type}"))
            except Exception:
                pass

        # Safe migration for settings table
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE settings ADD COLUMN ccp_account VARCHAR(100)"))
        except Exception:
            pass

        # Safe migration for referrals table
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE referrals ADD COLUMN settled_amount INTEGER DEFAULT 0"))
        except Exception:
            pass

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

        # Seed universities
        from app.models import University
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
            print("✅ Default universities created in database")


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

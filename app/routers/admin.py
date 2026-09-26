"""
Admin-only routes — protected by JWT with role='admin'.
Covers: login, overview stats, students CRUD, payments approve/reject,
vendors CRUD, offers CRUD, referrals list, settings, and demo seed.
"""
from datetime import datetime, timedelta
from typing import Optional, List
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app import models, schemas
from app.auth import (
    hash_password, verify_password, create_access_token, get_current_admin
)
from app.database import get_db
from app.image_utils import compress_image
from app.storage import upload_image
from app.config import ADMIN_EMAIL, ADMIN_PASSWORD, SUBSCRIPTION_PRICE_DZD

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── POST /api/admin/login ─────────────────────────────────────

@router.post("/login", response_model=schemas.Token)
async def admin_login(body: schemas.AdminLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.AdminUser).where(models.AdminUser.email == body.email)
    )
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(body.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="بيانات المشرف غير صحيحة"
        )
    token = create_access_token(str(admin.id), "admin")
    return schemas.Token(
        access_token=token,
        admin=schemas.AdminOut.model_validate(admin)
    )


# ── GET /api/admin/overview ───────────────────────────────────

@router.get("/overview", response_model=schemas.OverviewStats)
async def overview(
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    total_students = (await db.execute(select(func.count(models.Student.id)))).scalar() or 0
    active_subs = (await db.execute(
        select(func.count(models.Student.id)).where(models.Student.subscription_status == "active")
    )).scalar() or 0
    pending_pays = (await db.execute(
        select(func.count(models.Payment.id)).where(models.Payment.status == "pending")
    )).scalar() or 0
    total_vendors = (await db.execute(select(func.count(models.Vendor.id)))).scalar() or 0
    total_refs = (await db.execute(select(func.count(models.Referral.id)))).scalar() or 0
    total_ref_uses = (await db.execute(select(func.sum(models.Referral.usage_count)))).scalar() or 0

    return schemas.OverviewStats(
        total_students=total_students,
        active_subscriptions=active_subs,
        pending_payments=pending_pays,
        total_vendors=total_vendors,
        total_referrals=total_refs,
        total_referral_uses=total_ref_uses,
    )


# ── STUDENTS ──────────────────────────────────────────────────

@router.get("/students", response_model=List[schemas.StudentAdminOut])
async def list_students(
    q: Optional[str] = None,
    subscription_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(models.Student)
    if q:
        kw = f"%{q}%"
        stmt = stmt.where(
            models.Student.name.ilike(kw) | models.Student.phone.ilike(kw)
        )
    if subscription_status:
        stmt = stmt.where(models.Student.subscription_status == subscription_status)
    stmt = stmt.order_by(models.Student.registered_at.desc()).offset((page-1)*limit).limit(limit)
    result = await db.execute(stmt)
    return [schemas.StudentAdminOut.model_validate(s) for s in result.scalars().all()]


@router.get("/students/{student_id}", response_model=schemas.StudentAdminOut)
async def get_student(
    student_id: int,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Student).where(models.Student.id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail="الطالب غير موجود")
    return schemas.StudentAdminOut.model_validate(s)


@router.post("/students", response_model=schemas.StudentAdminOut, status_code=201)
async def add_student(
    body: schemas.StudentRegister,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(models.Student).where(models.Student.phone == body.phone))
    if existing.scalar_one_or_none():
        raise HTTPException(409, detail="رقم الهاتف مسجل مسبقاً")
    student = models.Student(
        name=body.name, phone=body.phone, university=body.university,
        password_hash=hash_password(body.password or "123456"),
        referral_code="TEMP",
    )
    db.add(student)
    await db.flush()
    student.referral_code = f"AM{body.name[:4].upper()}{student.id:04d}".replace(" ", "")
    db.add(models.Referral(student_id=student.id, code=student.referral_code))
    await db.commit()
    await db.refresh(student)
    return schemas.StudentAdminOut.model_validate(student)


@router.delete("/students/{student_id}", status_code=200)
async def delete_student(
    student_id: int,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Student).where(models.Student.id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail="الطالب غير موجود")
    await db.delete(s)
    await db.commit()
    return {"detail": "تم حذف الحساب بنجاح"}


class AmbassadorToggle(BaseModel):
    is_ambassador: bool

@router.patch("/students/{student_id}/ambassador", response_model=schemas.StudentAdminOut)
async def toggle_ambassador(
    student_id: int,
    body: AmbassadorToggle,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Student).where(models.Student.id == student_id))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail="الطالب غير موجود")
    
    s.is_ambassador = body.is_ambassador
    await db.commit()
    await db.refresh(s)
    return schemas.StudentAdminOut.model_validate(s)

# ── PAYMENTS ──────────────────────────────────────────────────

@router.get("/payments", response_model=List[schemas.PaymentOut])
async def list_payments(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(models.Payment)
        .options(selectinload(models.Payment.student))
        .order_by(models.Payment.submitted_at.desc())
    )
    if status_filter:
        stmt = stmt.where(models.Payment.status == status_filter)
    stmt = stmt.offset((page-1)*limit).limit(limit)
    result = await db.execute(stmt)
    out = []
    for p in result.scalars().all():
        row = schemas.PaymentOut.model_validate(p)
        row.student_name = p.student.name if p.student else ""
        row.student_phone = p.student.phone if p.student else ""
        out.append(row)
    return out


@router.post("/payments/{payment_id}/approve", response_model=schemas.PaymentOut)
async def approve_payment(
    payment_id: int,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Payment).options(selectinload(models.Payment.student))
        .where(models.Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, detail="طلب الدفع غير موجود")
    if payment.status != "pending":
        raise HTTPException(400, detail="تم البت في هذا الطلب مسبقاً")

    now = datetime.utcnow()
    payment.status = "approved"
    payment.reviewed_at = now
    payment.reviewed_by = admin.id

    # Set subscription — exactly +1 YEAR, not +1 month (bug fix from original prototype)
    student = payment.student
    student.subscription_status = "active"
    student.subscription_start = now
    student.subscription_end = now + timedelta(days=365)

    # Process referral reward if payment has a referral code
    if payment.referral_code:
        ref_result = await db.execute(
            select(models.Student).where(models.Student.referral_code == payment.referral_code)
        )
        referrer = ref_result.scalar_one_or_none()
        if referrer:
            ref_row = await db.execute(
                select(models.Referral).where(models.Referral.student_id == referrer.id)
            )
            ref_entry = ref_row.scalar_one_or_none()
            if ref_entry:
                ref_entry.usage_count += 1
                ref_entry.reward_amount += 200

    await db.commit()
    await db.refresh(payment)
    row = schemas.PaymentOut.model_validate(payment)
    row.student_name = student.name
    row.student_phone = student.phone
    return row


@router.post("/payments/{payment_id}/reject", response_model=schemas.PaymentOut)
async def reject_payment(
    payment_id: int,
    body: schemas.RejectPaymentIn,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Payment).options(selectinload(models.Payment.student))
        .where(models.Payment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(404, detail="طلب الدفع غير موجود")
    if payment.status != "pending":
        raise HTTPException(400, detail="تم البت في هذا الطلب مسبقاً")

    now = datetime.utcnow()
    payment.status = "rejected"
    payment.rejection_reason = body.reason
    payment.reviewed_at = now
    payment.reviewed_by = admin.id

    student = payment.student
    student.subscription_status = "rejected"

    await db.commit()
    await db.refresh(payment)
    row = schemas.PaymentOut.model_validate(payment)
    row.student_name = student.name
    row.student_phone = student.phone
    return row


# ── VENDORS ───────────────────────────────────────────────────

@router.get("/vendors", response_model=List[schemas.VendorOut])
async def list_vendors(
    q: Optional[str] = None,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(models.Vendor)
    if q:
        stmt = stmt.where(models.Vendor.name.ilike(f"%{q}%"))
    result = await db.execute(stmt.order_by(models.Vendor.created_at.desc()))
    vendors = result.scalars().all()
    out = []
    for v in vendors:
        d = schemas.VendorOut.model_validate(v)
        # Count associated offers
        cnt = await db.execute(
            select(func.count(models.Offer.id)).where(models.Offer.vendor_id == v.id)
        )
        d.offers_count = cnt.scalar() or 0
        out.append(d)
    return out


@router.post("/vendors", response_model=schemas.VendorOut, status_code=201)
async def add_vendor(
    body: schemas.VendorCreate,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    vendor = models.Vendor(**body.model_dump())
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)
    d = schemas.VendorOut.model_validate(vendor)
    d.offers_count = 0
    return d


@router.patch("/vendors/{vendor_id}", response_model=schemas.VendorOut)
async def update_vendor(
    vendor_id: int,
    body: schemas.VendorUpdate,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Vendor).where(models.Vendor.id == vendor_id))
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(404, detail="التاجر غير موجود")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(vendor, field, value)
    await db.commit()
    await db.refresh(vendor)
    d = schemas.VendorOut.model_validate(vendor)
    cnt = await db.execute(select(func.count(models.Offer.id)).where(models.Offer.vendor_id == vendor_id))
    d.offers_count = cnt.scalar() or 0
    return d
@router.delete("/vendors/{vendor_id}", status_code=200)
async def delete_vendor(
    vendor_id: int,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Vendor).where(models.Vendor.id == vendor_id))
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(404, detail="التاجر غير موجود")
    # You might want to delete related offers or mark them inactive.
    # For now, let's delete the vendor and rely on DB constraints or cascade.
    await db.delete(vendor)
    await db.commit()
    return {"message": "تم حذف التاجر بنجاح"}


# ── OFFERS ────────────────────────────────────────────────────

@router.get("/offers", response_model=List[schemas.OfferOut])
async def admin_list_offers(
    category: Optional[str] = None,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(models.Offer).options(selectinload(models.Offer.vendor))
    if category:
        stmt = stmt.where(models.Offer.category.contains(category))
    result = await db.execute(stmt.order_by(models.Offer.created_at.desc()))
    out = []
    for o in result.scalars().all():
        d = schemas.OfferOut.model_validate(o)
        d.vendor_name = o.vendor.name if o.vendor else ""
        d.vendor_address = o.vendor.address if o.vendor else ""
        out.append(d)
    return out


@router.post("/offers", response_model=schemas.OfferOut, status_code=201)
async def add_offer(
    body: schemas.OfferCreate,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    # Validate vendor exists
    v_res = await db.execute(select(models.Vendor).where(models.Vendor.id == body.vendor_id))
    vendor = v_res.scalar_one_or_none()
    if not vendor:
        raise HTTPException(404, detail="التاجر غير موجود")
    offer = models.Offer(**body.model_dump())
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    d = schemas.OfferOut.model_validate(offer)
    d.vendor_name = vendor.name
    d.vendor_address = vendor.address
    return d


@router.post("/offers/{offer_id}/image")
async def upload_offer_image(
    offer_id: int,
    file: UploadFile = File(...),
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Offer).where(models.Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(404, detail="العرض غير موجود")
    raw = await file.read()
    compressed, mime = compress_image(raw, file.content_type or "image/jpeg")
    url = await upload_image(compressed, mime, folder="offers")
    offer.image_url = url
    await db.commit()
    return {"image_url": url}


@router.patch("/offers/{offer_id}", response_model=schemas.OfferOut)
async def update_offer(
    offer_id: int,
    body: schemas.OfferUpdate,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Offer).options(selectinload(models.Offer.vendor))
        .where(models.Offer.id == offer_id)
    )
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(404, detail="العرض غير موجود")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(offer, field, value)
    await db.commit()
    await db.refresh(offer)
    d = schemas.OfferOut.model_validate(offer)
    d.vendor_name = offer.vendor.name if offer.vendor else ""
    d.vendor_address = offer.vendor.address if offer.vendor else ""
    return d


@router.delete("/offers/{offer_id}", status_code=200)
async def delete_offer(
    offer_id: int,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Offer).where(models.Offer.id == offer_id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(404, detail="العرض غير موجود")
    await db.delete(offer)
    await db.commit()
    return {"detail": "تم حذف العرض بنجاح"}


# ── REFERRALS ─────────────────────────────────────────────────

@router.get("/referrals", response_model=List[schemas.ReferralOut])
async def list_referrals(
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(models.Referral)
        .options(selectinload(models.Referral.student))
        .order_by(models.Referral.usage_count.desc())
    )
    out = []
    for r in result.scalars().all():
        row = schemas.ReferralOut.model_validate(r)
        row.student_name = r.student.name if r.student else ""
        out.append(row)
    return out


# ── SETTINGS ──────────────────────────────────────────────────

@router.get("/settings", response_model=schemas.SettingOut)
async def get_settings(
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Setting).limit(1))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail="الإعدادات غير مُهيأة بعد — شغّل seed أولاً")
    return schemas.SettingOut.model_validate(s)


@router.patch("/settings", response_model=schemas.SettingOut)
async def update_settings(
    body: schemas.SettingUpdate,
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(models.Setting).limit(1))
    s = result.scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail="الإعدادات غير مُهيأة — شغّل seed أولاً")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(s, field, value)
    s.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(s)
    return schemas.SettingOut.model_validate(s)


# ── DEMO SEED ─────────────────────────────────────────────────

@router.post("/seed-demo", status_code=200)
async def seed_demo(
    admin: models.AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Populates the database with rich demo data.
    Safe to call multiple times — will skip rows that already exist.
    """
    from app.auth import hash_password as hp
    from datetime import date

    # Settings
    settings_exists = await db.execute(select(models.Setting).limit(1))
    if not settings_exists.scalar_one_or_none():
        db.add(models.Setting(
            baridimob_account="0799 12 34 56",
            account_holder="محمد أمين بوكتاشة",
            payment_note="سيتم تفعيل اشتراكك خلال 24 ساعة من التحقق من الدفع",
            subscription_price=1000,
            admin_email=ADMIN_EMAIL,
            app_version="1.0.0",
        ))

    # Vendors
    vendors_data = [
        ("مطعم وشواء القلعة", "مطاعم وكافيهات", "036 84 12 30", "وسط مدينة سطيف — شارع أول نوفمبر"),
        ("نادي الأبطال للياقة البدنية", "رياضة", "0550 11 22 33", "حي المعبودة — سطيف"),
        ("مكتبة المعرفة الجامعية", "تعليم ومكتبات", "036 92 44 55", "بجانب القطب الجامعي فرحات عباس"),
        ("مقهى ومساحة عمل أرينا", "مطاعم وكافيهات", "0560 77 88 99", "حي الهضاب — سطيف"),
        ("مخبر التحاليل الطبية الشفاء", "خدمات", "036 82 10 20", "شارع 8 ماي 1945 — سطيف"),
    ]
    created_vendors = []
    for vname, vcat, vphone, vaddr in vendors_data:
        existing = await db.execute(select(models.Vendor).where(models.Vendor.name == vname))
        v = existing.scalar_one_or_none()
        if not v:
            v = models.Vendor(name=vname, category=vcat, phone=vphone, address=vaddr, active=True)
            db.add(v)
            await db.flush()
        created_vendors.append(v)

    # Offers
    offers_data = [
        (0, "خصم 25% على كافة وجبات الغداء والمشاوي", "مطاعم وكافيهات", 25,
         "assets/offers/offer_restaurant.jpg"),
        (1, "اشتراك شهري في القاعة الرياضية بـ 2000 دج بدل 3500 دج", "رياضة", 40,
         "assets/offers/offer_gym.jpg"),
        (2, "تخفيض 20% على الكتب والقرطاسية والمذكرات الجامعية", "تعليم ومكتبات", 20,
         "assets/offers/offer_bookstore.jpg"),
        (3, "خصم 15% على جميع المشروبات ومساحات الدراسة الهادئة", "مطاعم وكافيهات", 15,
         "assets/offers/offer_cafe.jpg"),
        (4, "تخفيض 30% على التحاليل الطبية الشاملة والفحوصات المخبرية", "خدمات", 30,
         "assets/offers/offer_medical.jpg"),
    ]
    created_offers = []
    for vid_idx, otitle, ocat, odisc, oimg in offers_data:
        existing = await db.execute(select(models.Offer).where(models.Offer.title == otitle))
        o = existing.scalar_one_or_none()
        if not o and vid_idx < len(created_vendors):
            o = models.Offer(
                vendor_id=created_vendors[vid_idx].id,
                title=otitle, category=ocat, discount_pct=odisc,
                image_url=oimg, active=True,
                start_date=date(2026, 9, 1), end_date=date(2027, 9, 1),
            )
            db.add(o)
            await db.flush()
        if o:
            created_offers.append(o)

    # Students (3 demo students)
    students_data = [
        ("محمد أمين بوكتاشة", "0555123456", "جامعة فرحات عباس - سطيف", "active"),
        ("سارة بلقاسم", "0666987654", "جامعة محمد لمين دباغين - سطيف 2", "active"),
        ("يوسف زروقي", "0777456789", "المدرسة العليا للتكنولوجيا - سطيف", "pending"),
    ]
    created_students = []
    for sname, sphone, suni, ssub in students_data:
        existing = await db.execute(select(models.Student).where(models.Student.phone == sphone))
        s = existing.scalar_one_or_none()
        if not s:
            s = models.Student(
                name=sname, phone=sphone, university=suni,
                password_hash=hp("Demo2026!"),
                referral_code="TEMP",
                subscription_status=ssub,
            )
            if ssub == "active":
                s.subscription_start = datetime(2026, 9, 1)
                s.subscription_end = datetime(2027, 9, 1)
            db.add(s)
            await db.flush()
            s.referral_code = f"AMENCO{s.id:02d}"
            db.add(models.Referral(
                student_id=s.id, code=s.referral_code,
                usage_count=max(0, 8 - len(created_students) * 3),
                reward_amount=max(0, (8 - len(created_students) * 3)) * 200,
            ))
        created_students.append(s)

    # Pending payment for student 3
    if created_students and len(created_students) >= 3:
        stu = created_students[2]
        existing_pay = await db.execute(
            select(models.Payment).where(models.Payment.student_id == stu.id)
        )
        if not existing_pay.scalar_one_or_none():
            db.add(models.Payment(
                student_id=stu.id,
                amount=1000,
                receipt_image_url="assets/illustrations/payment_receipt_mock.png",
                status="pending",
            ))

    # Second pending payment for student 1 (adds richness to admin queue)
    if created_students:
        stu2 = created_students[0]
        existing_old = await db.execute(
            select(models.Payment)
            .where(models.Payment.student_id == stu2.id, models.Payment.status == "approved")
        )
        if not existing_old.scalar_one_or_none():
            db.add(models.Payment(
                student_id=stu2.id,
                amount=1000,
                receipt_image_url="assets/illustrations/payment_receipt_mock.png",
                status="approved",
                reviewed_at=datetime(2026, 9, 1),
            ))

    await db.commit()
    return {
        "detail": "تم ملء قاعدة البيانات بالبيانات التجريبية بنجاح",
        "vendors": len(created_vendors),
        "offers": len(created_offers),
        "students": len(created_students),
    }

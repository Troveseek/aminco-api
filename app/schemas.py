"""
Pydantic schemas for all API request/response models.
Completely decoupled from SQLAlchemy — we never expose ORM objects directly.
"""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, field_validator, EmailStr
import re


# ──────────────────────────────────────────────
# CATEGORIES
# ──────────────────────────────────────────────

class CategoryBase(BaseModel):
    label: str
    icon: str

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(CategoryBase):
    pass

class CategoryOut(CategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# ──────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student: Optional["StudentOut"] = None
    admin: Optional["AdminOut"] = None


# ──────────────────────────────────────────────
# ADMIN
# ──────────────────────────────────────────────

class AdminLogin(BaseModel):
    email: str
    password: str


class AdminOut(BaseModel):
    id: int
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# STUDENTS
# ──────────────────────────────────────────────

ALGERIA_PHONE_RE = re.compile(r"^0[5-7]\d{8}$")

class StudentRegister(BaseModel):
    name: str
    phone: str
    university: str
    password: str
    referred_by_code: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_min_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("الاسم يجب أن يكون 3 أحرف على الأقل")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not ALGERIA_PHONE_RE.match(v):
            raise ValueError("رقم الهاتف غير صحيح — مثال صحيح: 0555123456")
        return v

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("كلمة المرور يجب أن تكون 6 أحرف على الأقل")
        return v

    @field_validator("university")
    @classmethod
    def university_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("الجامعة مطلوبة")
        return v


class StudentAdminCreate(BaseModel):
    name: str
    phone: str
    university: str
    password: str
    is_ambassador: bool = False
    plan_amount: int = 2000
    activate_now: bool = True
    note: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_min_length(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("الاسم يجب أن يكون 3 أحرف على الأقل")
        return v

    @field_validator("phone")
    @classmethod
    def phone_format(cls, v: str) -> str:
        v = v.strip().replace(" ", "")
        if not ALGERIA_PHONE_RE.match(v):
            raise ValueError("رقم الهاتف غير صحيح — مثال صحيح: 0555123456")
        return v

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 4:
            raise ValueError("كلمة المرور يجب أن تكون 4 أحرف على الأقل")
        return v


class StudentLogin(BaseModel):
    phone: str
    password: str

    @field_validator("phone")
    @classmethod
    def phone_clean(cls, v: str) -> str:
        return v.strip().replace(" ", "")


class StudentOut(BaseModel):
    id: int
    name: str
    phone: str
    university: str
    photo_url: Optional[str] = None
    subscription_status: str
    subscription_start: Optional[datetime] = None
    subscription_end: Optional[datetime] = None
    referral_code: str
    is_ambassador: bool = False
    registered_at: datetime

    model_config = {"from_attributes": True}


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    university: Optional[str] = None
    is_ambassador: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def name_min_length(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 3:
                raise ValueError("الاسم يجب أن يكون 3 أحرف على الأقل")
        return v


# Admin-facing student with extra fields
class StudentAdminOut(StudentOut):
    referred_by: Optional[int] = None


# ──────────────────────────────────────────────
# VENDORS
# ──────────────────────────────────────────────

class VendorCreate(BaseModel):
    name: str
    category: str
    phone: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    instagram_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    location_url: Optional[str] = None
    active: bool = True

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("اسم التاجر مطلوب")
        return v


class VendorUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    instagram_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    location_url: Optional[str] = None
    active: Optional[bool] = None


class VendorOut(BaseModel):
    id: int
    name: str
    category: str
    phone: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    instagram_url: Optional[str] = None
    tiktok_url: Optional[str] = None
    location_url: Optional[str] = None
    active: bool
    created_at: datetime
    offers_count: int = 0

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# OFFERS
# ──────────────────────────────────────────────

class OfferCreate(BaseModel):
    vendor_id: int
    title: str
    category: str
    discount_pct: int
    description: Optional[str] = None
    terms: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    active: bool = True

    @field_validator("discount_pct")
    @classmethod
    def discount_range(cls, v: int) -> int:
        if not (0 <= v <= 100):
            raise ValueError("نسبة الخصم يجب أن تكون بين 0 و 100")
        return v

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("عنوان العرض مطلوب")
        return v


class OfferUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    discount_pct: Optional[int] = None
    description: Optional[str] = None
    terms: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    active: Optional[bool] = None


class OfferOut(BaseModel):
    id: int
    vendor_id: int
    vendor_name: str = ""
    vendor_address: Optional[str] = None
    vendor_phone: Optional[str] = None
    vendor_instagram: Optional[str] = None
    vendor_tiktok: Optional[str] = None
    vendor_location: Optional[str] = None
    title: str
    category: str
    discount_pct: int
    image_url: Optional[str] = None
    description: Optional[str] = None
    terms: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    active: bool
    is_favorited: bool = False
    # locked = True means the offer requires an active subscription to see full details
    # For now all offers show to all logged-in users; non-subscribers see "subscribe" CTA
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# PAYMENTS
# ──────────────────────────────────────────────

class PaymentOut(BaseModel):
    id: int
    student_id: int
    student_name: str = ""
    student_phone: str = ""
    amount: int
    receipt_image_url: str
    status: str
    rejection_reason: Optional[str] = None
    submitted_at: datetime
    reviewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RejectPaymentIn(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("سبب الرفض مطلوب")
        return v


class CashPaymentIn(BaseModel):
    amount: int = 2000
    referral_code: Optional[str] = None


# ──────────────────────────────────────────────
# REFERRALS
# ──────────────────────────────────────────────

class ReferralOut(BaseModel):
    id: int
    student_id: int
    student_name: str = ""
    code: str
    usage_count: int
    reward_amount: int
    reward_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# SETTINGS
# ──────────────────────────────────────────────

class SettingOut(BaseModel):
    id: int
    baridimob_account: str
    account_holder: str
    payment_note: Optional[str] = None
    subscription_price: int
    admin_email: str
    app_version: Optional[str] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingUpdate(BaseModel):
    baridimob_account: Optional[str] = None
    account_holder: Optional[str] = None
    payment_note: Optional[str] = None
    subscription_price: Optional[int] = None


# ──────────────────────────────────────────────
# ADMIN OVERVIEW
# ──────────────────────────────────────────────

class OverviewStats(BaseModel):
    total_students: int
    active_subscriptions: int
    pending_payments: int
    total_vendors: int
    total_referrals: int
    total_referral_uses: int


# ──────────────────────────────────────────────
# VERIFY (public, vendor-facing)
# ──────────────────────────────────────────────

class VerifyOut(BaseModel):
    student_id: int
    name: str
    university: str
    phone: Optional[str] = None
    photo_url: Optional[str] = None
    subscription_status: str
    subscription_end: Optional[datetime] = None
    is_valid: bool   # True only if subscription_status == 'active' and not expired
    verified_at: datetime


# Fix forward reference
Token.model_rebuild()

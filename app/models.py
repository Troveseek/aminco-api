"""
SQLAlchemy async models — mirrors the §6 database schema exactly.
All tables use Integer primary keys (Supabase Postgres default).
"""
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, Integer, String, Text, Date,
    DateTime, ForeignKey, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    label      = Column(String(100), nullable=False, unique=True)
    icon       = Column(String(50), nullable=False, default="category")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class University(Base):
    __tablename__ = "universities"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    email         = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime, nullable=False, default=datetime.utcnow)


class Student(Base):
    __tablename__ = "students"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    name                = Column(String(255), nullable=False)
    phone               = Column(String(20), unique=True, nullable=False, index=True)
    university          = Column(String(255), nullable=False)
    password_hash       = Column(String(255), nullable=False)
    photo_url           = Column(Text, nullable=True)
    subscription_status = Column(
        String(20), nullable=False, default="none",
        # Checked in application layer too; DB constraint is the safety net
    )
    subscription_start  = Column(DateTime, nullable=True)
    subscription_end    = Column(DateTime, nullable=True)
    referral_code       = Column(String(20), unique=True, nullable=False)
    referred_by         = Column(Integer, ForeignKey("students.id"), nullable=True)
    is_ambassador       = Column(Boolean, nullable=False, default=False)
    registered_at       = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "subscription_status IN ('none','pending','active','rejected')",
            name="ck_student_subscription_status"
        ),
    )

    payments   = relationship("Payment", back_populates="student", cascade="all, delete-orphan")
    referrals  = relationship("Referral", back_populates="student", cascade="all, delete-orphan")
    favorites  = relationship("Favorite", back_populates="student", cascade="all, delete-orphan")


class Vendor(Base):
    __tablename__ = "vendors"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(255), nullable=False)
    category    = Column(String(100), nullable=False)
    phone         = Column(String(20), nullable=True)
    address       = Column(Text, nullable=True)
    description   = Column(Text, nullable=True)
    instagram_url = Column(String(255), nullable=True)
    tiktok_url    = Column(String(255), nullable=True)
    location_url  = Column(Text, nullable=True)
    active        = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime, nullable=False, default=datetime.utcnow)

    offers = relationship("Offer", back_populates="vendor", cascade="all, delete-orphan")


class Offer(Base):
    __tablename__ = "offers"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    vendor_id    = Column(Integer, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False)
    title        = Column(String(255), nullable=False)
    category     = Column(String(100), nullable=False, index=True)
    discount_pct = Column(Integer, nullable=False)
    image_url    = Column(Text, nullable=True)
    description  = Column(Text, nullable=True)
    terms        = Column(Text, nullable=True)
    start_date   = Column(Date, nullable=True)
    end_date     = Column(Date, nullable=True)
    active       = Column(Boolean, nullable=False, default=True, index=True)
    created_at   = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("discount_pct BETWEEN 0 AND 100", name="ck_offer_discount"),
    )

    vendor    = relationship("Vendor", back_populates="offers")
    favorites = relationship("Favorite", back_populates="offer", cascade="all, delete-orphan")


class Favorite(Base):
    __tablename__ = "favorites"

    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), primary_key=True)
    offer_id   = Column(Integer, ForeignKey("offers.id", ondelete="CASCADE"), primary_key=True)

    student = relationship("Student", back_populates="favorites")
    offer   = relationship("Offer", back_populates="favorites")


class Payment(Base):
    __tablename__ = "payments"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    student_id        = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    amount            = Column(Integer, nullable=False)
    receipt_image_url = Column(Text, nullable=False)
    status            = Column(String(20), nullable=False, default="pending")
    rejection_reason  = Column(Text, nullable=True)
    referral_code     = Column(String(50), nullable=True)
    submitted_at      = Column(DateTime, nullable=False, default=datetime.utcnow)
    reviewed_at       = Column(DateTime, nullable=True)
    reviewed_by       = Column(Integer, ForeignKey("admin_users.id"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected')",
            name="ck_payment_status"
        ),
    )

    student = relationship("Student", back_populates="payments")


class Referral(Base):
    __tablename__ = "referrals"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    student_id    = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    code          = Column(String(20), nullable=False)
    usage_count   = Column(Integer, nullable=False, default=0)
    reward_amount = Column(Integer, nullable=False, default=0)
    reward_status = Column(String(20), nullable=False, default="pending")
    created_at    = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "reward_status IN ('pending','settled')",
            name="ck_referral_reward_status"
        ),
    )

    student = relationship("Student", back_populates="referrals")


class Setting(Base):
    __tablename__ = "settings"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    baridimob_account  = Column(String(50), nullable=False, default="0799 12 34 56")
    account_holder     = Column(String(255), nullable=False, default="")
    payment_note       = Column(Text, nullable=True)
    subscription_price = Column(Integer, nullable=False, default=1000)
    admin_email        = Column(String(255), nullable=False, default="admin@amenco-club.dz")
    app_version        = Column(String(20), nullable=True, default="1.0.0")
    updated_at         = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

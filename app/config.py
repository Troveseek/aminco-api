import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./amenco.db"
)

JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE_ME_IN_PRODUCTION_PLEASE")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # 7 days

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@amenco-club.dz")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "AmencoAdmin2026!")

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")
SUBSCRIPTION_PRICE_DZD = int(os.getenv("SUBSCRIPTION_PRICE_DZD", "1000"))
SUBSCRIPTION_DURATION_YEARS = int(os.getenv("SUBSCRIPTION_DURATION_YEARS", "1"))

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")  # "supabase", "cloudinary", or "local"
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "amenco-uploads")

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")

MAX_IMAGE_SIZE_KB = int(os.getenv("MAX_IMAGE_SIZE_KB", "300"))

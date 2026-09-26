import asyncio
from app.database import SessionLocal
from app.models import AdminUser
from app.auth import hash_password
from sqlalchemy import select

async def main():
    async with SessionLocal() as db:
        result = await db.execute(select(AdminUser).where(AdminUser.email == "admin@amenco-club.dz"))
        admin = result.scalar_one_or_none()
        if admin:
            admin.hashed_password = hash_password("AmencoSecure2027!!")
            await db.commit()
            print("Admin password updated successfully to 'AmencoSecure2027!!'")
        else:
            print("Admin user not found!")

asyncio.run(main())

import sys
sys.stdout.reconfigure(encoding='utf-8')
from app.database import AsyncSessionLocal
from app.models import Student
from app.qr import generate_verify_qr_png
from app.storage import upload_qr_png
from sqlalchemy.future import select
import asyncio

async def regen():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Student))
        students = res.scalars().all()
        count = 0
        for st in students:
            qr_bytes = generate_verify_qr_png(st.id)
            path = await upload_qr_png(st.id, qr_bytes)
            st.qr_code_url = path
            count += 1
        await db.commit()
        print(f'Regenerated {count} QR codes.')

asyncio.run(regen())

# AMENCO Club Backend — Setup & Run Guide

## Prerequisites
- Python 3.8+ (already installed)
- A Supabase project (free tier is enough for demo)

---

## Step 1: Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) → New Project
2. Name it `amenco-club`, choose a region close to Algeria (e.g. Frankfurt)
3. Set a strong DB password, save it
4. After creation, go to **Project Settings → API** and copy:
   - `Project URL` → `SUPABASE_URL`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY`
   - `anon` key → `SUPABASE_ANON_KEY`
5. Go to **Project Settings → Database** and copy the connection string:
   - Use the **direct** connection (not pooled), change `[YOUR-PASSWORD]` to your DB password
   - Replace `postgres://` with `postgresql+asyncpg://`
   - Paste this as `DATABASE_URL`

---

## Step 2: Create Storage Bucket

In Supabase Dashboard → **Storage → New Bucket**:
- Name: `amenco-uploads`
- Public: ✅ (so uploaded images serve as public URLs)
- Click Create

---

## Step 3: Configure Environment

```bash
cd c:\Users\boukt\Downloads\beru213\backend
copy .env.example .env
# Now edit .env with your Supabase credentials
```

Edit `.env`:
```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
SUPABASE_ANON_KEY=eyJhbGci...
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.your-project-id.supabase.co:5432/postgres
JWT_SECRET=pick-any-long-random-string-here-at-least-32-chars
ADMIN_EMAIL=admin@amenco-club.dz
ADMIN_PASSWORD=AmencoAdmin2026!
APP_BASE_URL=http://localhost:8000
STORAGE_BACKEND=supabase
SUPABASE_STORAGE_BUCKET=amenco-uploads
```

---

## Step 4: Run the Backend

```bash
cd c:\Users\boukt\Downloads\beru213\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
✅ Admin user created: admin@amenco-club.dz
✅ Default settings created
```

Open in browser: **http://localhost:8000/docs** — you'll see the full interactive API.

---

## Step 5: Seed Demo Data

In the Swagger UI at `/docs`:
1. Click `POST /api/admin/login` → use your admin email/password → copy the `access_token`
2. Click **Authorize** (lock icon top right) → paste the token
3. Click `POST /api/admin/seed-demo` → Execute

Or via curl:
```bash
# Login
curl -X POST http://localhost:8000/api/admin/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@amenco-club.dz","password":"AmencoAdmin2026!"}'

# Seed (replace TOKEN with the access_token from login response)
curl -X POST http://localhost:8000/api/admin/seed-demo \
  -H "Authorization: Bearer TOKEN"
```

---

## Step 6: Deploy to Supabase Edge Functions (Optional) or External Host

For multi-device demo, deploy the FastAPI backend to Railway/Render:

### Railway (recommended — ~15 min setup)
1. Install Railway CLI: `npm i -g @railway/cli`
2. `railway login`
3. `cd backend && railway init`
4. Set environment variables via `railway variables set KEY=VALUE` for each `.env` key
5. `railway up` — Railway auto-detects Python and runs uvicorn

Update `APP_BASE_URL` in your Railway env vars to the deployed HTTPS URL.
Update `api.js` in the frontend to point to this URL.

---

## Backend File Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py          ← FastAPI app + startup
│   ├── config.py        ← All env vars in one place
│   ├── models.py        ← SQLAlchemy ORM models (8 tables)
│   ├── schemas.py       ← Pydantic request/response models
│   ├── auth.py          ← JWT + bcrypt
│   ├── database.py      ← Async session factory
│   ├── qr.py            ← Real QR code generation
│   ├── image_utils.py   ← Server-side compression
│   ├── storage.py       ← Supabase Storage upload
│   └── routers/
│       ├── students.py  ← Register/login/profile/QR
│       ├── offers.py    ← Browse/search/favorites
│       ├── payments.py  ← Receipt upload
│       ├── verify.py    ← Public vendor verification
│       └── admin.py     ← Full admin CRUD + seed
├── uploads/             ← Local image storage (dev mode only)
├── requirements.txt
├── .env.example
└── README.md            ← This file
```

---

## API Endpoint Summary

| Auth | Endpoint | Purpose |
|------|----------|---------|
| — | `POST /api/students/register` | Sign up |
| — | `POST /api/students/login` | Login |
| JWT (student) | `GET /api/students/me` | My profile |
| JWT (student) | `PATCH /api/students/me` | Edit profile |
| JWT (student) | `POST /api/students/me/photo` | Upload photo |
| JWT (student) | `GET /api/students/{id}/qr` | Real QR PNG |
| — | `GET /api/offers` | Browse offers |
| JWT (student) | `POST/DELETE /api/favorites/{id}` | Toggle favorite |
| JWT (student) | `POST /api/payments/upload` | Submit receipt |
| — | `GET /verify/{id}` | Vendor verification |
| — | `POST /api/admin/login` | Admin login |
| JWT (admin) | `GET /api/admin/overview` | Dashboard stats |
| JWT (admin) | `GET/POST /api/admin/students` | Student CRUD |
| JWT (admin) | `POST /api/admin/payments/{id}/approve` | Approve payment |
| JWT (admin) | `POST /api/admin/payments/{id}/reject` | Reject with reason |
| JWT (admin) | `GET/POST /api/admin/vendors` | Vendor CRUD |
| JWT (admin) | `GET/POST /api/admin/offers` | Offer CRUD |
| JWT (admin) | `GET /api/admin/referrals` | Referrals list |
| JWT (admin) | `GET/PATCH /api/admin/settings` | Platform settings |
| JWT (admin) | `POST /api/admin/seed-demo` | Seed demo data |

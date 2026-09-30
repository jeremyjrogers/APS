# APS

Proof-of-concept advanced planning system for a single-plant pump/compressor
manufacturer running two lines: Engineer/Configure-to-Order new-unit
packages, and aftermarket parts manufacturing + repair/overhaul.

Goal: ~80% of Kinaxis RapidResponse-style planning capability at a fraction
of the cost, built for a single plant.

See [docs/domain-model.md](docs/domain-model.md) for the full domain model.

## Phased scope

1. Supply/production planning engine (current focus)
2. What-if scenario simulation (including capable-to-promise quoting)
3. S&OP dashboard / exception management
4. Concurrent (instant-renet) planning — deferred, evaluate after 1-3

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL
- **Frontend**: React, TypeScript, Vite
- **Local infra**: Docker Compose (Postgres)

## Getting started

### Database

```bash
docker compose up -d postgres
```

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

API health check: `GET http://localhost:8000/health`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Deploying (Render, free tier)

`render.yaml` at the repo root defines a Blueprint: free Postgres, a Python
web service for the backend, and a static site for the frontend.

1. Push this repo to GitHub (Render deploys from a repo, not a local
   checkout).
2. In the Render dashboard: **New > Blueprint**, point it at the repo. It
   reads `render.yaml` and creates all three resources in one go.
3. Once the backend is live, seed the database once. Free web services have
   no Shell/SSH access, so do this from your own machine against the
   *external* database URL instead (Render dashboard → `aps-db` → External
   Database URL — different from the internal one the backend service uses):
   ```bash
   cd backend
   source .venv/bin/activate
   DATABASE_URL="<external database URL from the Render dashboard>" python scripts/seed.py --reset
   ```
   Setting `DATABASE_URL` inline like this only affects that one command —
   your local `.env` (pointing at your local Docker Postgres) is untouched.
   Do this once after the first deploy — it's a full reset, not something to
   run on every deploy.
4. Visit the `aps-frontend` service's URL. On the Overview tab, click "Run
   Planning" to confirm it's actually talking to the seeded database.

**Known limitations of the free tier:**
- Free Postgres expires 30 days after creation (14-day grace period after
  that before deletion). For a short-lived demo this is fine; for anything
  longer, upgrade the database plan (~$7/mo) before day 30.
- The free backend spins down after 15 min idle; the first request after
  that takes about a minute to wake it back up. The frontend (a static site)
  has no such delay.
- Free web services have no Shell/SSH access and no one-off jobs — hence
  seeding from your local machine against the external DB URL instead of
  in-dashboard.
- `CORS_ORIGINS` and `VITE_API_BASE` in `render.yaml` are hardcoded to the
  services' predictable `https://<name>.onrender.com` URLs (Render's
  Blueprint cross-service references only expose private-network addressing,
  which a browser can't reach). If either service name collides with an
  existing Render service and gets auto-suffixed, update the corresponding
  env var to match and redeploy — the frontend one needs a rebuild since
  Vite bakes it in at build time, not just a restart.

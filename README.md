# APS

**Live demo:** https://aps-frontend-xek6.onrender.com — hosted on Render's
free tier (see [Deploying](#deploying-render-free-tier) below). Give the
backend a few seconds to wake up if it's been idle; the "Run Planning"
button explains this if you hit it while it's still spinning up.

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
web service for the backend, and a static site for the frontend. The current
live deployment:

- Frontend: https://aps-frontend-xek6.onrender.com
- Backend: https://aps-backend-q9br.onrender.com (`/health`, `/docs`)
- Both names got auto-suffixed by Render because `aps-backend` and
  `aps-frontend` were already taken by unrelated services — expect the same
  on a fresh deploy under those names; `-xek6`/`-q9br` are specific to this
  deployment, not something Render will reassign to you.

### First-time setup

1. Push this repo to GitHub (Render deploys from a repo, not a local
   checkout).
2. In the Render dashboard: **New > Blueprint**, point it at the repo. It
   reads `render.yaml` and creates all three resources in one go.
3. **Check the actual assigned URLs** for the backend and frontend services
   (dashboard → each service → URL shown near the top). If either got
   suffixed (likely — `aps-backend`/`aps-frontend` are common enough names to
   collide), the `CORS_ORIGINS` and `VITE_API_BASE` values baked into
   `render.yaml` will be wrong. Fix this **before** step 4:
   - Backend service → **Environment** tab → set `CORS_ORIGINS` to the
     frontend's actual URL.
   - Frontend service → **Environment** tab → set `VITE_API_BASE` to the
     backend's actual URL, then **Manual Deploy → Deploy latest commit** (Vite
     bakes this in at build time, so saving the env var alone doesn't
     rebuild it).
   - **Editing `render.yaml` and pushing does not auto-apply env var changes
     to already-created services** — confirmed the hard way. A normal code
     push does trigger a rebuild/redeploy fine; it's specifically Blueprint
     env var edits after initial creation that need the manual dashboard
     step above. Once fixed, update the values in `render.yaml` too so the
     file matches reality for the next person reading it.
4. Seed the database once. Free web services have no Shell/SSH access, so do
   this from your own machine against the *external* database URL instead
   (Render dashboard → `aps-db` → External Database URL — different from the
   internal one the backend service uses):
   ```bash
   cd backend
   source .venv/bin/activate
   DATABASE_URL="<external database URL from the Render dashboard>" python scripts/seed.py --reset
   ```
   Setting `DATABASE_URL` inline like this only affects that one command —
   your local `.env` (pointing at your local Docker Postgres) is untouched.
   Do this once after the first deploy — it's a full reset, not something to
   run on every deploy.
5. Visit the frontend URL. On the Overview tab, click "Run Planning" to
   confirm it's actually talking to the seeded database.

**Known limitations of the free tier:**
- Free Postgres expires 30 days after creation (14-day grace period after
  that before deletion). For a short-lived demo this is fine; for anything
  longer, upgrade the database plan (~$7/mo) before day 30.
- The free backend spins down after 15 min idle; the first request after
  that takes about a minute to wake it back up (the frontend has a note
  about this on the "Run Planning" button). The frontend itself, as a static
  site, has no such delay.
- Free web services have no Shell/SSH access and no one-off jobs — hence
  seeding from your local machine against the external DB URL instead of
  in-dashboard.
- Render's Blueprint `fromService` env var references only expose
  private-network addressing (a hostname only reachable from other Render
  services, not from a user's browser). `CORS_ORIGINS` and `VITE_API_BASE`
  are plain hardcoded URLs in `render.yaml` for this reason, not
  `fromService` references.

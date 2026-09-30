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

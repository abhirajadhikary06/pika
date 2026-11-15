# Pika

Pika is a modern, multi-tenant helpdesk and customer support platform built for teams. It supports workspaces, role-based access, tickets, conversations, internal notes, notifications, dashboards, and background jobs — with an architecture designed to evolve into an offline-first PWA.

## Architecture

| Layer | Technology |
|-------|------------|
| Frontend | React 18 + TypeScript + Vite + Tailwind + TanStack Query + React Hook Form + Zod |
| Backend | Python 3.12 + Flask + SQLAlchemy + Flask-JWT-Extended + Celery |
| Database | PostgreSQL (Neon in production) |
| Broker | Memory transport (local) / Upstash Redis (production) |
| Deploy | Vercel (frontend) · Render (API + worker) · Neon · Upstash |

Services are independently deployable. Tenant isolation is enforced at the API layer via workspace membership checks.

## Features

- User registration, JWT auth (access + refresh with revocation)
- Workspaces, roles (owner / admin / agent / viewer), invitations
- Tickets: create, assign, prioritize, status workflow, tags, search/filter/sort/pagination
- Comments & internal notes, activity audit trail
- In-app notifications
- Dashboard with workload stats
- Celery tasks for SMTP email notifications and cleanup
- Rate limiting, CORS, structured logging, health/readiness probes
- Alembic migrations, pytest suite, GitHub Actions CI
- Docker Compose for local full-stack
- Architecture ready for offline-first PWA (client_id idempotency, version columns, timestamps)

## Project structure

```
pika/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Auth, workspaces, tickets, notifications
│   │   ├── models/          # SQLAlchemy models
│   │   ├── tasks/           # Celery tasks
│   │   ├── utils/           # Auth, errors, validators
│   │   ├── config.py
│   │   └── __init__.py      # App factory
│   ├── migrations/
│   ├── tests/
│   ├── Dockerfile
│   ├── wsgi.py
│   ├── celery_worker.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── lib/             # API client, auth context, utils
│   │   ├── types/
│   │   └── assets/          # Logos (128 / 256 / 512)
│   ├── public/
│   └── package.json
├── docker-compose.yml
├── .github/workflows/ci.yml
└── README.md
```

## Quick start (local)

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16 (or use Docker Compose / Neon free tier)

### 1. Database

```bash
# Local Postgres example
createdb pika_dev
# Or set DATABASE_URL to a Neon connection string
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY

# Run migrations
export FLASK_APP=wsgi.py
flask db upgrade   # or: python -c "from app import create_app, db; app=create_app(); app.app_context().push(); db.create_all()"

# API
python run.py
# → http://localhost:5000

# Worker (separate terminal; memory broker needs no Redis)
celery -A celery_worker.celery worker --loglevel=info
```

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # leave VITE_API_URL empty for Vite proxy
npm run dev
# → http://localhost:5173
```

### Docker Compose (API + Postgres + worker)

```bash
docker compose up --build
# API: http://localhost:5000
# Frontend still runs via npm run dev against the API
```

## Environment variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL URL (Neon or local) |
| `SECRET_KEY` | Flask secret |
| `JWT_SECRET_KEY` | JWT signing key |
| `CELERY_BROKER_URL` | `memory://` local · Upstash `rediss://...` prod |
| `CELERY_RESULT_BACKEND` | Same as broker or `cache+memory://` |
| `CORS_ORIGINS` | Comma-separated frontend origins |
| `FRONTEND_URL` | Public frontend URL used in invitation links |
| `SMTP_HOST`, `SMTP_PORT` | SMTP server connection |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | SMTP credentials |
| `SMTP_FROM` | From address for application email |
| `SMTP_USE_TLS` | Enable SMTP STARTTLS (`true`/`false`) |
| `FLASK_ENV` | `development` / `production` / `testing` |

### Frontend

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Empty in dev (proxy) · full API base URL in production |

## Testing

```bash
# Backend
cd backend
pytest -v

# Frontend
cd frontend
npm run typecheck
npm run test
npm run build
```

## Deployment

### Neon (PostgreSQL)

1. Create a project at [neon.tech](https://neon.tech)
2. Copy the connection string → `DATABASE_URL`
3. Run migrations against production: `FLASK_ENV=production flask db upgrade`

### Upstash (Redis)

1. Create a Redis database at [upstash.com](https://upstash.com)
2. Use the TLS URL for `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`

### Render (API + Worker)

1. Connect the repo
2. Use `backend/render.yaml` blueprint or create:
   - **Web service**: root `backend`, start `gunicorn ... wsgi:app`
   - **Background worker**: start `celery -A celery_worker.celery worker --loglevel=info`
3. Set env vars (DATABASE_URL, CELERY_*, SECRET_KEY, JWT_SECRET_KEY, CORS_ORIGINS)

### Vercel (Frontend)

1. Import `frontend` directory
2. Set `VITE_API_URL=https://<your-render-api>/api/v1`
3. Update `vercel.json` rewrite destination to your API URL
4. Deploy

### Post-deploy

- Confirm `/health` and `/ready` on the API
- Register a user, create a workspace, open a ticket
- Check worker logs for task execution

## API overview

Base: `/api/v1`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register |
| POST | `/auth/login` | Login → tokens |
| POST | `/auth/refresh` | Refresh access token |
| POST | `/auth/logout` | Revoke refresh token |
| GET/PATCH | `/auth/me` | Current user |
| GET/POST | `/workspaces` | List / create |
| GET/PATCH | `/workspaces/:id` | Get / update |
| GET | `/workspaces/:id/members` | Members |
| POST | `/workspaces/:id/invitations` | Invite |
| GET/POST | `/workspaces/:id/tickets` | List / create tickets |
| GET/PATCH | `/workspaces/:id/tickets/:tid` | Get / update |
| GET/POST | `/workspaces/:id/tickets/:tid/comments` | Comments |
| GET | `/workspaces/:id/stats` | Dashboard stats |
| GET | `/notifications` | List notifications |
| POST | `/invitations/:token/accept` | Accept an invitation for the authenticated invitee |
| POST | `/workspaces/:id/tickets/:tid/attachments` | Upload a ticket attachment |
| GET | `/workspaces/:id/tickets/:tid/attachments/:aid` | Download a ticket attachment |

Invitation links are delivered through the configured SMTP server and open the frontend
acceptance flow. Ticket attachments use the configured `UPLOAD_FOLDER`; production deployments
should mount durable storage for that directory.

All workspace-scoped routes require a valid JWT and active membership.

## Offline-first / PWA readiness

The schema and API already support future offline sync:

- UUID primary keys
- `client_id` on tickets/comments for idempotent client-generated creates
- `version` integer columns for optimistic concurrency
- Consistent `created_at` / `updated_at` timestamps
- Stateless JWT + refresh token store
- No hard online-only assumptions in the React data layer (TanStack Query + centralized client)

Future work: service worker, IndexedDB, background sync queue, conflict resolution UI, push notifications.

## License

MIT

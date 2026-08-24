# All in Bloom

Frontend and backend are fully separated:
- `Next.js` in `src/` is UI only.
- `FastAPI` in `fastapi/` owns all business logic, auth, database, email, Stripe, delivery, and uploads.

## Architecture
- Browser calls only `/api/*` on Next.js origin.
- Next.js rewrites `/api/*` to FastAPI.
- FastAPI handles auth (`JWT access token + httpOnly refresh cookie`) and data access.

## Frontend setup (Next.js)
1. Copy `.env.example` to `.env`.
2. Install dependencies:
   - `npm install`
3. Run:
   - `npm run dev`

## Backend setup (FastAPI)
1. Copy `fastapi/.env.example` to `fastapi/.env`.
2. Create database and run migrations:
   - `cd fastapi`
   - `alembic upgrade head`
3. Optional seed:
   - `python scripts/seed.py`
4. Run API:
   - `uvicorn app.main:app --reload --port 8000`

## Tests
### Frontend
- Run all frontend unit tests:
  - `npm run test`
- Run tests in watch mode:
  - `npm run test:watch`
- Generate coverage report:
  - `npm run test:coverage`

### Backend
- Open backend directory:
  - `cd fastapi`
- Run backend unit tests:
  - `python -m unittest discover -s tests -v`

## Docker
For a complete local application stack (Next.js, FastAPI, PostgreSQL,
migrations, and sample data), install Docker Desktop and run from the
repository root:

```bash
docker compose up --build
```

If your Docker installation provides the legacy Compose command instead, replace
`docker compose` with `docker-compose` in the commands below.

Open:
- Storefront: http://localhost:3000
- FastAPI liveness endpoint: http://localhost:8000/health
- FastAPI readiness endpoint (includes a database check): http://localhost:8000/ready

pgAdmin is an opt-in local development tool. Start it only when needed:

```bash
docker compose --profile tools up --build
```

It is then available at http://localhost:5050. The default pgAdmin login is
`admin@allinbloom.us` / `allinbloom-local-admin`.
Its preconfigured server is named **All in Bloom local PostgreSQL**; use the
PostgreSQL password `allinbloom_local_password_change_me` when pgAdmin asks for
it. If you change the database name or credentials in `compose.env`, update the
saved pgAdmin connection (host: `postgres`) to use the same values.

The payment-recovery scheduler is also opt-in locally. It checks pending
provider payments and delivers durable confirmation notifications at least once
per minute; run exactly one instance for a database:

```bash
docker compose --profile workers up --build
```

The backend waits for PostgreSQL, takes a PostgreSQL advisory lock, runs the
migrations, then loads sample data only into a fresh empty database. Existing
local data is preserved on later `docker compose up` runs. PostgreSQL, FastAPI,
and pgAdmin ports are bound to `127.0.0.1`, so they are not exposed to the local
network.

To customize ports, local credentials, the admin email, or optional provider
keys, copy the template and start Compose with it:

```bash
cp compose.env.example compose.env
docker compose --env-file compose.env up --build
```

On Windows PowerShell, replace `cp` with `Copy-Item`. Without a configured
Resend or Google provider, sign-in intentionally remains unavailable; this stack
does not add an insecure development-login bypass. If `AUTH_SECRET` is left
blank, the backend generates a temporary local secret on each restart.

To reset **all** local PostgreSQL and pgAdmin data, stop the stack and remove its
volumes:

```bash
docker compose down -v
```

## Production operations

`docker-compose.yml` is intentionally development-only: it uses localhost
URLs, development mode, and optional local credentials. Do not deploy it to a
public host. Production rollout, readiness, backup/restore, image-digest, and
shared-rate-limit requirements are in [the operations runbook](docs/operations.md).

# All in Bloom FastAPI Backend

## Requirements
- Python 3.11+
- PostgreSQL

## Setup
1. Open backend directory:
   ```bash
   cd fastapi
   ```
2. Copy `.env.example` to `.env` and fill in values.
3. Install dependencies:
   ```bash
   pip install -r requirements.lock
   ```
4. Run migrations through the concurrency-safe runner:
   ```bash
   python scripts/run_migrations.py
   ```
5. Seed data (optional):
   ```bash
   python scripts/seed.py
   ```
6. Start API:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

## Auth
- Email OTP: `POST /api/auth/request-code` -> `POST /api/auth/verify-code`
- Google sign-in: `POST /api/auth/google`
- Google sign-in state bootstrap: `POST /api/auth/google/state`
- Google sign-in fallback (OAuth code exchange): `POST /api/auth/google/code`
- Refresh token: `httpOnly` cookie (`POST /api/auth/refresh`)
- Logout: `POST /api/auth/logout`

## Integration
Next.js frontend should proxy `/api/*` traffic to this service.

## Docker

From the repository root, `docker compose up --build` starts PostgreSQL,
automatically applies migrations, seeds an empty database, starts this API, and
also provides the Next.js frontend and pgAdmin. See the root `README.md` for
ports, local credentials, optional integrations, and reset instructions.

## Production security requirements

- Set `ENVIRONMENT=production` explicitly, use an HTTPS `SITE_URL`, and provide a unique `AUTH_SECRET` of at least 32 characters. The API refuses to start with an omitted environment, placeholder secret, or non-HTTPS production site URL.
- Configure a signed Cloudinary preset plus `CLOUDINARY_API_KEY` and `CLOUDINARY_API_SECRET`. Keep all three server-side; never expose them as `NEXT_PUBLIC_*` variables.
- Configure an ingress/reverse-proxy body limit as a second line of defense. The application limits normal JSON requests and webhooks to 1 MiB and image uploads to approximately 5.125 MiB before multipart parsing.
- Use `/health` only for liveness and `/ready` for readiness. `/ready` returns `503` while PostgreSQL cannot execute a query, so load balancers must remove that replica from traffic.
- Run `python scripts/run_migrations.py` as the release migration job. For Railway, configure it as the **Pre-deploy Command**, set `RUN_MIGRATIONS_ON_START=false`, and keep the start command to Uvicorn only. PostgreSQL deployments serialize concurrent replicas with an advisory lock; set `MIGRATION_LOCK_TIMEOUT_SECONDS` if the default 120 seconds is unsuitable.
- The in-process rate limiter is a bounded emergency backstop. Enforce the authoritative public rate limit at a shared WAF/API gateway or Redis layer before scaling to multiple workers.
- `requirements.lock` pins the complete resolved Python dependency set and its artifact hashes; Docker and CI install it with `--require-hashes`. Regenerate it with `uv pip compile --generate-hashes --no-cache --no-emit-index-url requirements.txt` whenever `requirements.txt` changes.

## Tests
Run backend unit tests from the `fastapi` directory:

```bash
python -m unittest discover -s tests -v
```

## Critical error logging
Backend includes structured critical logging for:
- payment
- messaging
- personal data input validation
- auth
- admin access control
- cart/checkout validation

Configure via env:
- `LOG_LEVEL` (default `INFO`)
- `BETTERSTACK_SOURCE_TOKEN` (empty disables Better Stack shipping)
- `BETTERSTACK_INGEST_URL` (default `https://in.logs.betterstack.com`, or your source ingesting host)

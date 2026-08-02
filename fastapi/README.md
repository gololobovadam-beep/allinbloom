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
   pip install -r requirements.txt
   ```
4. Run migrations:
   ```bash
   alembic upgrade head
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

## Production security requirements

- Set `ENVIRONMENT=production` explicitly, use an HTTPS `SITE_URL`, and provide a unique `AUTH_SECRET` of at least 32 characters. The API refuses to start with an omitted environment, placeholder secret, or non-HTTPS production site URL.
- Keep `CLOUDINARY_UPLOAD_PRESET` server-side; do not expose it as a `NEXT_PUBLIC_*` variable.
- Configure an ingress/reverse-proxy body limit as a second line of defense. The application limits normal JSON requests and webhooks to 1 MiB and image uploads to approximately 5.125 MiB before multipart parsing.

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

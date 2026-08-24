#!/bin/sh
set -eu

# A local stack can start without committing a reusable JWT signing secret.
# Production must fail closed instead of silently accepting a generated key.
if [ -z "${AUTH_SECRET:-}" ]; then
  case "${ENVIRONMENT:-}" in
    production|prod)
      echo "AUTH_SECRET must be supplied in production." >&2
      exit 1
      ;;
    *)
      export AUTH_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
      echo "AUTH_SECRET was not supplied; generated a temporary development secret."
      ;;
  esac
fi

case "${RUN_MIGRATIONS_ON_START:-true}" in
  true|TRUE|1|yes|YES)
    echo "Applying database migrations..."
    python scripts/run_migrations.py
    ;;
  false|FALSE|0|no|NO)
    echo "RUN_MIGRATIONS_ON_START is disabled; migrations must run in the release step."
    ;;
  *)
    echo "RUN_MIGRATIONS_ON_START must be true or false." >&2
    exit 1
    ;;
esac

# Never put demo data into a newly created production database by default.
# The development Compose service opts in explicitly with SEED_DATABASE=true.
case "${SEED_DATABASE:-false}" in
  true|TRUE|1|yes|YES)
    should_seed="$(python - <<'PY'
from app.core.database import SessionLocal
from app.models.bouquet import Bouquet
from app.models.promo_slide import PromoSlide
from app.models.review import Review
from app.models.user import User

db = SessionLocal()
try:
    is_fresh_database = all(
        db.query(model).count() == 0
        for model in (Bouquet, PromoSlide, Review, User)
    )
    print("true" if is_fresh_database else "false")
finally:
    db.close()
PY
)"
    if [ "$should_seed" = "true" ]; then
      echo "Database is empty; loading sample data..."
      python scripts/seed.py
    else
      echo "Database already contains store data; skipping seed."
    fi
    ;;
  false|FALSE|0|no|NO)
    echo "SEED_DATABASE is disabled; skipping sample data."
    ;;
  *)
    echo "SEED_DATABASE must be true or false." >&2
    exit 1
    ;;
esac

exec "$@"

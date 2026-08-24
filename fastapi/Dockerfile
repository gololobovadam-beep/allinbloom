# syntax=docker/dockerfile:1

# Pin the multi-platform manifest so a rebuild cannot silently receive a
# different base image.
FROM python:3.12.13-slim-trixie@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY requirements.lock ./
RUN python -m pip install --no-cache-dir --disable-pip-version-check --require-hashes -r requirements.lock

COPY . .
RUN addgroup --system app && adduser --system --ingroup app app \
    && chmod +x /app/scripts/docker-entrypoint.sh /app/scripts/run_payment_jobs.sh \
    && chown -R app:app /app

USER app
EXPOSE 8000

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

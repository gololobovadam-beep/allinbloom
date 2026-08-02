from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth_router,
    bouquets_router,
    catalog_router,
    checkout_router,
    contact_router,
    delivery_router,
    orders_router,
    paypal_router,
    promotions_router,
    reviews_router,
    settings_router,
    stripe_webhook_router,
    upload_router,
    users_router,
)
from app.core.config import settings
from app.core.critical_logging import infer_domain_from_path, log_critical_event, setup_critical_logging
from app.core.request_size_limit import RequestBodyLimitMiddleware

setup_critical_logging()

app = FastAPI(title="All in Bloom FastAPI")

# Install the stream limiter before request parsing. CORS is added afterward
# so browser clients also receive CORS headers on early 413 responses.
app.add_middleware(RequestBodyLimitMiddleware)

origins = [
    settings.resolved_site_url(),
]
if settings.is_development():
    origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(origins)),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

app.include_router(auth_router)
app.include_router(bouquets_router)
app.include_router(catalog_router)
app.include_router(checkout_router)
app.include_router(contact_router)
app.include_router(delivery_router)
app.include_router(orders_router)
app.include_router(paypal_router)
app.include_router(promotions_router)
app.include_router(reviews_router)
app.include_router(settings_router)
app.include_router(stripe_webhook_router)
app.include_router(upload_router)
app.include_router(users_router)


@app.middleware("http")
async def log_unhandled_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        log_critical_event(
            domain=infer_domain_from_path(request.url.path),
            event="unhandled_exception",
            message="Unhandled server exception.",
            request=request,
            context={"path": request.url.path},
            exc=exc,
        )
        raise


@app.on_event("startup")
def validate_runtime_config() -> None:
    settings.validate_runtime_configuration()


@app.get("/health")
def health():
    return {"ok": True}

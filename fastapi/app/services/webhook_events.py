from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.webhook_event import WebhookEvent


_WEBHOOK_LEASE_SECONDS = 5 * 60


def is_webhook_event_processed(db: Session, *, provider: str, event_id: str) -> bool:
    """Return true only for a completed event, not an in-flight delivery."""
    if not event_id:
        return False
    existing = db.execute(
        select(WebhookEvent.id).where(
            WebhookEvent.provider == provider,
            WebhookEvent.event_id == event_id,
            WebhookEvent.status == "PROCESSED",
        )
    ).first()
    return existing is not None


def claim_webhook_event(db: Session, *, provider: str, event_id: str) -> bool:
    """Atomically claim an event before any provider side effect is performed.

    A unique provider/event key is the replay guard. A short lease lets a
    provider retry after a worker crash without allowing two concurrent
    deliveries to capture a payment or create duplicate timeline entries.
    """
    if not event_id:
        return False

    now = datetime.now(timezone.utc)
    try:
        with db.begin_nested():
            db.add(
                WebhookEvent(
                    provider=provider,
                    event_id=event_id,
                    status="PROCESSING",
                    claimed_at=now,
                )
            )
            db.flush()
        db.commit()
        return True
    except IntegrityError:
        # The savepoint is rolled back by begin_nested, preserving the caller's
        # transaction for a safe read/reclaim below.
        pass

    stale_before = now - timedelta(seconds=_WEBHOOK_LEASE_SECONDS)
    existing = db.execute(
        select(WebhookEvent).where(
            WebhookEvent.provider == provider,
            WebhookEvent.event_id == event_id,
        )
    ).scalar_one_or_none()
    if not existing or existing.status == "PROCESSED":
        return False

    reclaimed = db.execute(
        update(WebhookEvent)
        .execution_options(synchronize_session=False)
        .where(
            WebhookEvent.id == existing.id,
            WebhookEvent.status.in_(("PROCESSING", "RETRY")),
            or_(WebhookEvent.claimed_at.is_(None), WebhookEvent.claimed_at <= stale_before),
        )
        .values(status="PROCESSING", claimed_at=now, processed_at=None)
    )
    if reclaimed.rowcount:
        db.commit()
        return True
    db.rollback()
    return False


def mark_webhook_event_processed(db: Session, *, provider: str, event_id: str) -> None:
    if not event_id:
        return
    now = datetime.now(timezone.utc)
    updated = db.execute(
        update(WebhookEvent)
        .where(WebhookEvent.provider == provider, WebhookEvent.event_id == event_id)
        .values(status="PROCESSED", processed_at=now)
    )
    if not updated.rowcount:
        # Safe for direct callers during a rolling deployment where an old
        # process has not claimed the event first.
        try:
            with db.begin_nested():
                db.add(
                    WebhookEvent(
                        provider=provider,
                        event_id=event_id,
                        status="PROCESSED",
                        claimed_at=now,
                        processed_at=now,
                    )
                )
                db.flush()
        except IntegrityError:
            pass
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def release_webhook_event_claim(db: Session, *, provider: str, event_id: str) -> None:
    """Allow a transient provider error to be retried immediately."""
    if not event_id:
        return
    db.execute(
        update(WebhookEvent)
        .where(
            WebhookEvent.provider == provider,
            WebhookEvent.event_id == event_id,
            WebhookEvent.status == "PROCESSING",
        )
        # A known transient failure should be eligible on the provider's next
        # delivery immediately. A crashed PROCESSING worker still uses the
        # normal lease timeout above. Keep claimedAt non-null for the schema.
        .values(
            status="RETRY",
            claimed_at=datetime.now(timezone.utc)
            - timedelta(seconds=_WEBHOOK_LEASE_SECONDS + 1),
        )
    )
    db.commit()

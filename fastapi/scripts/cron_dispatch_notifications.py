"""Dispatch durable order notifications.

Run this from the platform scheduler at least once per minute. Webhooks attempt
an immediate delivery too, but this worker is the recovery path for provider,
mail, process, and network failures.
"""

from __future__ import annotations

import asyncio
import logging

from app.core.database import SessionLocal
from app.services.payment_notifications import dispatch_pending_order_notifications


logging.basicConfig(level=logging.INFO)


async def main() -> None:
    db = SessionLocal()
    try:
        delivered = await dispatch_pending_order_notifications(db, limit=100)
        logging.info("Dispatched %s order notification(s).", delivered)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())

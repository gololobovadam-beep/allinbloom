#!/bin/sh
set -eu

# This container is a scheduler, not an API worker. Each invocation below is a
# short-lived recovery job; keep exactly one scheduler replica per database.
interval="${CRON_INTERVAL_SECONDS:-60}"
case "$interval" in
  ''|*[!0-9]*|0)
    echo "CRON_INTERVAL_SECONDS must be a positive whole number." >&2
    exit 1
    ;;
esac

while :; do
  python scripts/cron_sync_orders.py
  python scripts/cron_dispatch_notifications.py
  sleep "$interval"
done

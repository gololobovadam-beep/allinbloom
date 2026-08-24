# Production operations runbook

This document is a release requirement for the application. The root
`docker-compose.yml` is for local development only and must not be exposed to
the internet.

## Release sequence

1. Build from the committed lock files and digest-pinned base images.
2. Scan the built images and dependency locks, then deploy the new migration
   runner once: `python scripts/run_migrations.py`. On Railway, make this the
   service's **Pre-deploy Command**, set `RUN_MIGRATIONS_ON_START=false`, and
   use a start command that only launches Uvicorn. Do not put `alembic upgrade`
   in the start command: a blocked database lock would prevent the API from
   listening and take the whole storefront offline.
3. Roll out application replicas. The runner also takes a PostgreSQL advisory
   lock, so an accidental concurrent start cannot run Alembic in parallel.
4. Route traffic only after `GET /ready` returns `200`. Keep `GET /health` as
   the liveness probe so an unavailable database does not cause a restart loop.
5. Monitor migration failures, readiness failures, payment-provider webhooks,
   and reconciliation/outbox job lag. Alert on every sustained non-zero value.

The container entrypoint defaults `SEED_DATABASE` to `false`; leave it disabled
in production. Local Compose opts in to the sample data explicitly.

## Payment recovery scheduling

- Run `scripts/cron_sync_orders.py` and
  `scripts/cron_dispatch_notifications.py` as **separate short-lived jobs at
  least once per minute**. Run exactly one scheduler per database; the order
  synchronizer additionally uses a PostgreSQL advisory lock.
- On a container platform, use two singleton CronJobs/scheduled tasks rather
  than an API replica. Give them the same database, payment-provider, email,
  and logging secrets as the backend, but no public ingress.
- Local Compose provides the opt-in `payment-jobs` worker profile for
  development (`docker compose --profile workers up`). It runs both short-lived
  jobs every `CRON_INTERVAL_SECONDS` (default 60). It is not a substitute for
  a managed production scheduler.

## Payment-provider webhook setup and release checks

Configure the provider dashboards before enabling either payment method in a
production environment. Use HTTPS endpoints that are reachable only through
the public edge:

- Stripe: `POST /api/stripe/webhook` with
  `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
  `checkout.session.async_payment_failed`, `checkout.session.expired`,
  `payment_intent.succeeded`, `payment_intent.payment_failed`,
  `payment_intent.canceled`, `charge.refunded`, and
  `charge.dispute.created`, `charge.dispute.updated`, `charge.dispute.closed`.
- PayPal: `POST /api/paypal/webhook` with
  `CHECKOUT.ORDER.APPROVED`, `CHECKOUT.ORDER.COMPLETED`,
  `CHECKOUT.ORDER.VOIDED`, `PAYMENT.CAPTURE.COMPLETED`,
  `PAYMENT.CAPTURE.DECLINED`, `PAYMENT.CAPTURE.DENIED`,
  `PAYMENT.CAPTURE.REFUNDED`, `PAYMENT.CAPTURE.REVERSED`,
  `PAYMENT.REFUND.COMPLETED`, `PAYMENT.REFUND.FAILED`, and
  `CUSTOMER.DISPUTE.CREATED`, `CUSTOMER.DISPUTE.UPDATED`,
  `CUSTOMER.DISPUTE.RESOLVED`.

`PAYMENT.REFUND.COMPLETED` is required: its refund-object ID is the financial
idempotency key. A capture-refunded notification without that ID is retained
for reconciliation but does not alter the refund total. In production, use
live Stripe credentials plus the matching webhook secret, and set all PayPal
credentials/webhook ID with `PAYPAL_ENV=live`; startup rejects partial or
mismatched payment configuration. It also requires `RESEND_API_KEY`,
`ADMIN_EMAIL`, and `EMAIL_FROM` while a production payment provider is enabled,
so confirmations cannot be silently discarded.

Before every provider credential or webhook change, run this sandbox checklist:

1. Complete a card and a PayPal payment, then resend each successful webhook;
   verify one paid order, one queued confirmation per recipient, and no
   duplicate outbox rows.
2. Decline a Stripe card, retry within the same open Checkout session, and
   verify the order remains pending until a terminal session event or success.
3. Cancel both provider flows and verify the guest checkout-access cookie can
   close only its matching order.
4. Issue a partial refund and resend/correlate both PayPal refund webhook
   types; verify the ledger has one refund fact and the order total is not
   double-counted. Repeat for a full refund and a dispute event.

## Database and backup controls

- Use a managed PostgreSQL service with TLS, private network access, encrypted
  storage, point-in-time recovery, and a separate least-privilege application
  role.
- Keep automated encrypted backups outside the primary account/region. Retain
  daily backups for at least 35 days and monthly backups according to the
  business retention policy.
- Test a full restore (including Alembic version, orders, payment events, and
  notification outbox) at least quarterly. Record the recovery time and data
  point objectives from the test.
- Never hard-delete financial records during an operational cleanup; use the
  application's archival/redaction flow instead.

## Edge and network controls

- Terminate TLS before the application and set `TRUST_PROXY_HEADERS=true` only
  when that proxy strips client-supplied forwarding headers and injects its own.
- Enforce shared IP/account limits at the CDN/WAF or a Redis-backed gateway for
  checkout, delivery quotes, OTP, contact, uploads, and webhook endpoints. The
  bounded process-local limiter is not a cross-replica security boundary.
- Restrict database ingress to application workloads, restrict egress to the
  payment, email, maps, logging, and image providers in use, and rotate all
  provider credentials through a secret manager.

## Supply-chain routine

- Keep Docker `FROM` and Compose images pinned by digest. Update a digest only
  after reviewing the vendor release and image scan result.
- Update `fastapi/requirements.txt`, regenerate its hash-locked
  `requirements.lock`, update the npm lockfile, and review audit output in one
  pull request.
- CI runs frontend tests/build/audit, backend tests, real PostgreSQL migrations,
  Python dependency audit, and Compose syntax validation. Protect the default
  branch with these checks.

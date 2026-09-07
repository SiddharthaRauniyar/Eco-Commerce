# Phase 18 — Operation guides

This is the short, task-oriented guide for running Secure Commerce. The phase
documents linked below remain the source of truth for the detailed business,
security, API, and deployment rules.

## Implemented scope and operator-provided services

The customer, staff, security, and API routes in this guide are implemented in
this repository. The supplied Compose stack also implements PostgreSQL, Redis,
Gunicorn, Nginx, migrations/static collection, readiness checks, and an
on-demand validated backup job.

The following are deliberately external operational responsibilities, not
bundled application services: public DNS, certificate issuance/TLS termination,
SMTP delivery, payment-provider accounts and webhook registration, job
scheduling, alerting, and off-host backup replication. Stripe and PayPal flows
are implemented but remain unavailable to customers until their credentials
and signed public webhooks are configured. There is no Celery worker or
always-on scheduler container; schedule the documented maintenance commands
from the controlled deployment host.

## Local installation

### Prerequisites

- Python 3.12 or later and `pip`.
- A free local TCP port 8000.

PostgreSQL, Redis, Docker, SMTP, and payment-provider accounts are not needed
for the default local setup. Development uses SQLite, an in-memory cache, and
the console email backend; verification and reset links are printed in the
terminal.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python manage.py migrate
python manage.py seed_roles
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/> for the storefront and
<http://127.0.0.1:8000/admin/> for Django admin. The server uses
`config.settings.development` unless `DJANGO_SETTINGS_MODULE` is set.

Before handing a change to another environment, run:

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

## Customer guide

| Need | Where | Notes |
| --- | --- | --- |
| Browse the store | `/` or `/shop/` | Browse categories at `/shop/category/<slug>/` and products at `/shop/<slug>/`. |
| Create or verify an account | `/accounts/register/` | Email verification activates the account; use `/accounts/verification/resend/` if needed. |
| Sign in, reset a password, or use MFA | `/accounts/login/`, `/accounts/password-reset/`, `/accounts/mfa/setup/` | MFA setup is available after sign-in. |
| View or change the cart | `/cart/` | Prices, discounts, tax, and availability are recalculated on the server. |
| Save items | `/wishlist/` | Requires a signed-in account. |
| Checkout | `/cart/checkout/` | Guest checkout is supported. Cash on delivery is always available; Stripe and PayPal appear only after their server-side configuration is complete. |
| View orders and invoices | `/orders/` | Account holders see their own history. A guest confirmation remains available only in the browser session that completed checkout. |

At an eligible order detail page, a signed-in customer can cancel, reorder, or
submit a return/refund request. Those actions are intentionally subject to the
current order and payment state. An online-payment browser return is not proof
of payment: the provider's signed notification is authoritative.

See the detailed [authentication guide](../security/phase-3-authentication.md),
[checkout guide](../operations/phase-7-shopping-checkout.md),
[payment guide](../operations/phase-8-payments.md), and
[order-management guide](../operations/phase-9-order-management.md).

## Staff and administrator guide

### First-time staff setup

Run `python manage.py seed_roles` after migrations, then create a superuser or
assign users to the supplied Django groups through `/admin/`. The seed command
is safe to run again when permissions change. Use a named, least-privilege
staff account for routine work; reserve superuser access for recovery.

The role definitions and permission scopes are documented in the
[authentication and RBAC guide](../security/phase-3-authentication.md).

### Work surfaces

| Surface | URL | Access and intended use |
| --- | --- | --- |
| Django admin | `/admin/` | The authoritative editing surface for catalog, inventory, orders, accounts, coupons, reviews, support tickets, and content. Django permissions still apply. |
| Operations overview | `/operations/` | Staff-only, permission-filtered operational snapshot. It is read-only and links to the appropriate admin records. |
| Staff workspace | `/operations/staff/` | Staff-only navigation into the admin apps the current user may access. |
| Reports | `/reports/?range=30` | Staff-only, permission-filtered reporting for `7`, `30`, or `90` days. Exports are `/reports/export/csv/`, `/reports/export/xlsx/`, and `/reports/export/pdf/` with the same `range` query parameter. |
| Security monitoring | `/security/monitoring/` | Requires `security.view_securityevent`; resolving an event additionally requires `security.change_securityevent`. |
| Security assurance | `/security/assurance/` | Requires `vulnerability_testing.view_vulnerabilityreport`; running a safe control check additionally requires the model's add permission. |

### Routine workflows

- **Catalog and inventory:** manage categories, products, variants, images, and
  reorder levels in Django admin. An exact product or variant stock edit creates
  an inventory adjustment audit row; alternatively add an **Inventory
  adjustment** for exactly one product or variant. Existing ledger rows cannot
  be edited or deleted. Use the stock-health filter for low inventory.
- **Orders and requests:** use the Orders and Order requests admin sections to
  update operational fulfillment/tracking fields and review customer requests.
  Immutable customer snapshots and order line items remain read-only.
- **Payments:** payment records are evidence, not a manual reconciliation
  screen. Do not create, edit, or delete them in Django admin; process provider
  changes through the verified payment/webhook flow and the provider's approved
  operational process.
- **Reviews, support, promotions, and content:** moderate reviews, work the
  support queue, activate/deactivate coupons, and publish content only when the
  assigned role grants those Django permissions.
- **Security evidence:** audit logs, activity logs, login attempts, and
  vulnerability reports are read-oriented. Resolve security events through the
  monitoring page or its audited admin action rather than editing their
  evidence.

For the underlying workflows, see the [inventory guide](../operations/phase-6-product-inventory-management.md),
[operations dashboard guide](../operations/phase-10-admin-dashboard.md),
[reports guide](../operations/phase-11-reports-analytics.md),
[security-monitoring guide](../security/phase-13-security-monitoring-dashboard.md),
and [security-assurance guide](../security/phase-14-vulnerability-testing.md).

## API users

The versioned JSON API begins at `/api/v1/`. It is for approved first-party or
integrated clients, not a replacement for browser checkout or staff
operations. Its JWT login, throttling, ownership rules, endpoint list, and
token lifetimes are documented in the [REST API guide](../api/phase-15-rest-api.md).

## Production deployment and operations

### External prerequisites

- Docker Engine with Docker Compose v2 on the deployment host.
- A public DNS name and a controlled TLS terminator in front of the Compose
  stack. Nginx is bound only to `127.0.0.1:8080`; the TLS terminator must send
  `X-Forwarded-Proto: https` before traffic reaches Nginx. The supplied Nginx
  configuration does not obtain or terminate certificates.
- A real SMTP provider and verified sender address for verification, password
  reset, and order email.
- Securely generated secrets and a protected way to store `.env`.
- If online payments are enabled: verified Stripe and/or PayPal credentials,
  public HTTPS webhook URLs, and a host scheduler for expired payment cleanup.
- A controlled off-host backup destination and a scheduled restore drill.

Copy the template, replace every placeholder, and restrict the real file to
the deployment account. At minimum, configure real Django hosts/origins,
PostgreSQL and Redis credentials, SMTP settings, `CHECKOUT_TAX_RATE`, and a
real `DJANGO_SECRET_KEY`. Generate and retain a stable `MFA_ENCRYPTION_KEY`
before enabling MFA in production. Use a separate `JWT_SIGNING_KEY` if API
token-key separation is required.

```sh
cp .env.example .env
# Edit .env with real values; do not commit it.
chmod 600 .env
docker compose config
docker compose up --build -d
docker compose ps
docker compose logs -f web
```

The web container runs migrations and `collectstatic` before Gunicorn starts.
Once the controlled TLS layer is configured, check readiness without exposing
dependency details:

```sh
curl --fail --silent --show-error \
  -H 'Host: your-public-host.example' \
  -H 'X-Forwarded-Proto: https' \
  http://127.0.0.1:8080/health/
```

Replace `your-public-host.example` with a hostname in `DJANGO_ALLOWED_HOSTS`.
Do not expose the Django `web` container, PostgreSQL, or Redis directly. Enable
HSTS only after every required hostname is working through HTTPS.
`DJANGO_TRUST_PROXY_HEADERS=true` is required by the production settings: keep
the `web` service internal, and configure Nginx `realip` only for a known
upstream proxy CIDR if that proxy forwards client IP addresses.

### Ongoing operations

```sh
# Interactive, one-time administrator creation after the stack is healthy.
docker compose exec web python manage.py createsuperuser

# Re-sync supplied groups after a release that changes model permissions.
docker compose exec -T web python manage.py seed_roles

# Run from the host scheduler when Stripe or PayPal is enabled.
docker compose exec -T web python manage.py expire_pending_payments

# Run a validated PostgreSQL backup maintenance job.
docker compose --profile maintenance run --rm backup
```

Schedule `expire_pending_payments` at an interval shorter than
`PAYMENT_RESERVATION_MINUTES` (30 minutes by default) whenever online payments
are enabled. Schedule the backup command daily only after a manual backup and
a non-production restore drill succeed. The detailed TLS, proxy, backup,
retention, and restore requirements are in the
[deployment runbook](../operations/phase-17-deployment.md); the performance
and Redis-cache behavior is in the
[performance guide](../operations/phase-16-performance.md).

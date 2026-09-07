# Phase 18 — Testing and quality assurance

## Current automated baseline

The project uses Django's built-in test runner and `django.test.TestCase`.
Each run creates and destroys an isolated test database.  Browser-facing
requests use Django's test client or DRF's `APIClient`; external email uses the
in-memory email backend where delivery is asserted; and Stripe checkout is
stubbed where a provider redirect would otherwise be required.

The full suite was run for this phase with:

```sh
python3 manage.py test --verbosity 1
```

It completed successfully: **52 tests ran in 17.338 seconds**, Django's system
check reported no issues, and the test database was destroyed afterwards.
This is local execution evidence, not a claim that production infrastructure
or a real payment provider was exercised.

There is currently no pytest configuration, browser end-to-end suite, coverage
threshold, load suite, or CI workflow in the repository.  Those are explicit
release risks to address when the deployment process needs automated gating.

## Test strategy

The automated checks prioritize state-changing commerce paths and trust
boundaries over superficial template snapshots:

- Model and service behaviour covers immutable inventory adjustments, checkout
  idempotency, payment completion, and order transitions.
- Request-level integration checks cover server-rendered routes, permissions,
  session/JWT authentication, email side effects, and HTTP headers.
- Targeted negative checks cover inactive catalog visibility, invalid uploads,
  expired checkout tokens, lockouts, unauthorized ownership access, and
  forbidden staff/security actions.
- A small performance regression set asserts query counts for catalog/detail
  loading, variant rendering, order history, and public API caching.

The tests intentionally use the existing Django facilities.  They do not
attempt to simulate a browser engine, real Redis/PostgreSQL/Nginx, live SMTP,
or Stripe's network.  Those dependencies belong in the integration and UAT
checks below.

## Automated suite inventory

| Area | Source | Tests | What the suite proves |
| --- | --- | ---: | --- |
| Project configuration | `config/tests.py` | 2 | Development media routing resolves to `MEDIA_ROOT`; branded Django admin loads its custom styling and dashboard copy. |
| Accounts and RBAC | `apps/accounts/tests.py` | 5 | Registration starts inactive, verification activates the account, MFA requires a valid TOTP before session login, password reset sends mail, and role synchronization does not over-grant catalog permissions. |
| Storefront and catalog | `apps/core/tests.py`, `apps/products/tests.py` (`PublicCatalogTests`) | 6 | Health responds only with `{"status": "ok"}`; public views hide drafts; category/search/detail routes work; public catalog and variant selectors keep bounded query counts. |
| Inventory | `apps/products/tests.py` | 4 | Product and variant adjustments use the ledger, cannot go negative, retain before/after audit data, and an admin exact-stock edit does not bypass the ledger. |
| Cart and checkout | `apps/cart/tests.py` | 5 | Server-calculated coupon totals, guest COD checkout, stock reservation, order-email contents, idempotency, checkout-token expiry, wishlist access, and variant-form query count are checked. |
| Payments | `apps/payments/tests.py` | 3 | Stripe checkout creates a pending reserved order before redirect; a valid repeated webhook completes once; expired online payments release stock and reactivate the cart. |
| Customer orders | `apps/orders/tests.py` | 5 | Owner-only access, one-time cancellation with stock release, return/refund requests, reorder, annotated history counts, and stable PDF invoices are checked. |
| Operations and reports | `apps/admin_dashboard/tests.py`, `apps/analytics/tests.py` | 6 | Staff see authorized metrics/tools; customers are denied; reports show paid totals; CSV/XLSX/PDF exports parse and exclude customer email. |
| Application security | `apps/security/tests.py` | 7 | Trusted-proxy handling, nonce CSP/security headers, login lockouts, upload allow-listing, security-monitor permissions, and audited resolution are checked. |
| Security assurance workspace | `apps/vulnerability_testing/tests.py` | 2 | Authorized analysts record six non-exploiting control reports; observers cannot start a run. |
| REST API | `apps/api/tests.py` | 7 | Public JSON allow-lists, catalog visibility/cache invalidation, no private API route, JWT rotation/revocation, MFA/lockout, and owner-scoped customer resources are checked. |

The table totals 52 tests.  Individual test names are intentionally the most
precise current specification; run a focused module with the commands below
before changing the behaviour it protects.

## Representative expected results

These examples summarize real assertions rather than adding a second,
independent specification.

- `AuthenticationFlowTests.test_registration_verification_activates_account_and_creates_profile` expects a new account to remain inactive and unverified, creates a profile, sends one email, then activates/verifies only after the signed link is visited.
- `InventoryAdjustmentTests.test_adjustment_cannot_make_stock_negative` expects a validation error, unchanged stock, and no adjustment record when an adjustment would take stock below zero.
- `CartCheckoutTests.test_guest_cod_checkout_reserves_stock_creates_order_and_is_idempotent` expects one order/payment, a two-unit stock reservation, one confirmation email containing the order/product, an inactive cart, and no duplicate order when the same idempotency key is retried.
- `PaymentFlowTests.test_verified_stripe_webhook_marks_the_order_paid_only_once` sends the same correctly signed local webhook twice and expects a succeeded payment, a paid order, unchanged post-reservation stock, and one email.
- `CustomerOrderTests.test_reorder_uses_current_prices_and_customer_orders_are_private` expects another user to receive `404` for an order and the owner to receive a new cart line rather than a copied private order.
- `SecurityImplementationTests.test_repeated_failed_logins_lock_the_account_identifier_and_create_an_event` expects `429`, a `Retry-After` value, failed-login records, and a high-severity lockout event after the configured failure threshold.
- `PublicCatalogAPITests.test_catalog_returns_only_public_allowlisted_json` expects JSON that omits stock, reorder level, metadata, SKU, permissive CORS, and session cookies.
- `PublicCatalogAPITests.test_default_catalog_response_is_cached_and_invalidated_after_a_commit` expects the second unfiltered catalog request to need zero database queries and a committed catalog change to refresh the response.
- `ReportsTests.test_export_formats_are_parseable_and_exclude_customer_email` expects CSV, XLSX, and PDF exports to be usable while excluding the customer's email address.

## Commands for developers

From the repository root, install the declared dependencies and run the normal
suite:

```sh
python3 -m pip install .
python3 manage.py test --verbosity 1
```

Run a focused area while making a related change:

```sh
python3 manage.py test apps.accounts.tests
python3 manage.py test apps.products.tests apps.cart.tests apps.orders.tests apps.payments.tests
python3 manage.py test apps.api.tests apps.security.tests apps.vulnerability_testing.tests
python3 manage.py test apps.admin_dashboard.tests apps.analytics.tests config.tests apps.core.tests
```

Run low-cost release checks before a merge or deployment:

```sh
python3 manage.py check
python3 manage.py makemigrations --check --dry-run
```

When the production Compose stack is configured with a real `.env`, validate
the rendered service configuration and production deployment checks without
using development settings:

```sh
docker compose config
docker compose exec web python manage.py check --deploy
```

`docker compose exec` requires a running `web` service.  Do not replace real
production secrets with the placeholders in `.env.example`; production
settings intentionally reject those values.

## Integration checklist

Perform these checks in a staging environment that matches the production
Compose topology before public traffic is enabled.

- [ ] Start the stack with a real, protected `.env`; confirm PostgreSQL and
  Redis become healthy before the web service starts.
- [ ] Confirm `docker compose logs -f web` shows successful migrations and
  `collectstatic`, with no missing-manifest errors.
- [ ] Through the trusted TLS terminator, request `https://<host>/health/` and
  expect HTTP 200 with exactly `{"status":"ok"}`.  Do not expose the Django
  `web` port directly.
- [ ] Create a catalog product with an uploaded image and verify Nginx serves
  the media URL, while a fresh deployment serves collected static assets.
- [ ] Configure the SMTP provider and verify registration, password-reset,
  guest COD confirmation, and successful online-payment confirmation reach a
  controlled mailbox with correct links and order details.
- [ ] With the real Redis URL, verify an unfiltered public API catalog response
  has the expected cache header, a later request is a cache hit, and a product
  edit becomes visible after the committed invalidation.
- [ ] Use Stripe test mode only: start checkout, deliver a provider-generated
  signed event to the webhook endpoint, and confirm duplicate delivery does
  not duplicate payment completion, stock changes, or email.
- [ ] Run `docker compose --profile maintenance run --rm backup`, validate the
  dump, and restore it into a non-production database following the Phase 17
  restore drill.
- [ ] Re-run the full Django suite against the intended database engine when
  the delivery environment supports a disposable PostgreSQL test database.

## Security and privacy checklist

- [ ] Confirm public HTTPS redirects, secure session/CSRF cookies, host
  validation, and `DJANGO_TRUST_PROXY_HEADERS=true` only behind the controlled
  proxy described in the deployment runbook.
- [ ] Inspect a representative HTML response for a nonce-based
  `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, and
  `X-Frame-Options: DENY`; verify the policy does not require
  `unsafe-inline`.
- [ ] Attempt direct URL/API access as a customer to staff dashboard, reports,
  security-monitoring actions, another user's orders, addresses, and wishlist.
  Expect the tested `403`/`404` ownership and permission behaviour.
- [ ] Attempt browser and API sign-in with unverified accounts, an enrolled MFA
  account without/with an invalid code, and repeated bad credentials.  Confirm
  rejection/lockout logging, `Retry-After`, and no authenticated session/token
  before a valid challenge succeeds.
- [ ] Upload harmless malformed content labelled as an image and confirm it is
  rejected.  Test approved image formats at the configured size boundary using
  a staging-only account.
- [ ] Send an invalid payment-webhook signature in the provider's test
  environment and confirm no payment/order state changes.  The automated suite
  covers accepted signed and duplicate events; this negative provider path is
  a manual staging check.
- [ ] Check export downloads and staff screens for accidental customer PII;
  the automated report test specifically asserts that customer email is absent,
  but it is not a complete privacy audit.
- [ ] Verify `.env`, backups, database files, and generated media are not
  committed, and rotate any secret that was ever used outside its intended
  environment.

## User acceptance checklist

- [ ] A visitor can navigate the homepage, catalog search/category pages, and
  active product detail without seeing draft products.
- [ ] A customer can register, receive and use email verification, optionally
  enroll in MFA, reset a password, and sign in/out using keyboard navigation.
- [ ] A shopper can add/update/remove products, apply a valid coupon, save an
  item to a wishlist after sign-in, and see server-calculated totals.
- [ ] A guest can complete a COD purchase, receive an order email, access only
  their own confirmation session, and not create a duplicate order by
  refreshing or resubmitting checkout.
- [ ] A customer can view only their own order history/detail, cancel an
  eligible order once, request return/refund where eligible, reorder current
  catalog items, and download a stable invoice PDF.
- [ ] A catalog administrator can set an exact stock quantity in Django admin
  and see a corresponding inventory adjustment rather than a silent direct
  stock overwrite.
- [ ] An authorized staff user can use the operations workspace, view paid
  sales/low-stock information, and download CSV/XLSX/PDF reports without
  customer email data; a customer cannot access those paths.
- [ ] A security analyst can view/resolve an event with an audit trail and run
  the safe assurance report; a view-only observer cannot perform either
  state-changing action.
- [ ] Check the primary flows at phone and desktop widths, with keyboard-only
  navigation, visible focus, the theme control, and a screen reader where
  available.  No automated browser accessibility test currently replaces this
  review.

## Release gate and known limits

Do not call a release ready until the full suite, Django checks, migration
drift check, staging integration checklist, security checklist, and relevant
UAT checks all pass.  Record the commit, environment, tester, command output,
and any accepted exception with the release record.

Known limits today:

- The 52 tests are Django integration-style `TestCase` checks using the local
  default configuration; they are not a coverage measurement.
- No CI workflow automatically runs these commands on every change.
- No browser automation covers JavaScript/theme behaviour, responsive layout,
  or assistive-technology behaviour.
- No automated test currently starts Docker, Nginx, PostgreSQL, Redis, SMTP,
  or a live Stripe sandbox.  Phase 17's Compose validation and backup work
  require the staging checks above.
- The current query-count assertions are useful regression signals, but they
  are not load, concurrency, or capacity tests.

Ponytail Lite note: this single runbook documents the real suite and manual
gates already needed; add CI, browser automation, coverage thresholds, or load
testing only when the deployment/release process can run and act on them.

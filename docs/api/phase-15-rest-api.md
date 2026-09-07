# Phase 15 — REST API

`/api/v1/` is a JSON-only API for first-party applications and approved
integrations. It uses DRF pagination, a 60/minute anonymous throttle, a
120/minute authenticated throttle, and no permissive CORS policy.

## Authentication

`POST /api/v1/auth/token/` accepts JSON with `email`, `password`, and (only for
an enrolled account) `mfa_code`. It applies the same failed-login audit trail,
account lockout, email-verification rule, and TOTP validation as the browser
sign-in flow.

Use the resulting access token for private calls:

```http
Authorization: Bearer <access-token>
```

Access tokens expire after 15 minutes. Refresh tokens expire after one day.
`POST /api/v1/auth/token/refresh/` rotates a refresh token and invalidates the
old one. `POST /api/v1/auth/token/revoke/` accepts `{ "refresh": "..." }` to
revoke it. A lockout response is `429` with `Retry-After`.

## Endpoints

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/categories/` | public | Active category list |
| `GET` | `/products/?q=&category=&sort=&page=` | public | Active catalog, paginated; sorts: `newest`, `price_low`, `price_high`, `name` |
| `GET` | `/products/{slug}/` | public | Public product detail |
| `POST` | `/auth/token/` | public | MFA-aware JWT sign-in |
| `POST` | `/auth/token/refresh/` | public | Rotate refresh token |
| `POST` | `/auth/token/revoke/` | public | Revoke refresh token |
| `GET`, `PATCH` | `/me/` | token/session | Read or update own display name |
| `GET`, `POST` | `/addresses/` | token/session | List or create own address |
| `GET`, `PATCH`, `DELETE` | `/addresses/{id}/` | token/session | Manage own address |
| `GET`, `POST` | `/wishlist/` | token/session | Read wishlist or add `{ "product_slug": "..." }` |
| `DELETE` | `/wishlist/products/{slug}/` | token/session | Remove saved product |
| `GET` | `/orders/` | token/session | Own order history |
| `GET` | `/orders/{order_number}/` | token/session | Own order detail |
| `POST` | `/orders/{order_number}/cancel/` | token/session | Cancel through the existing order service |
| `POST` | `/orders/{order_number}/return/` | token/session | Submit `{ "reason": "..." }` |
| `POST` | `/orders/{order_number}/refund/` | token/session | Submit `{ "reason": "..." }` |

Catalog responses deliberately omit exact inventory, reorder levels, SKUs,
metadata, product status, storage fields, payments, staff data, and customer
address snapshots. Customer queries are always scoped to the authenticated
user, returning `404` rather than revealing another account's record.

Cart, checkout, payment initiation, payment webhooks, invoices, staff
operations, and security-monitoring data remain on their existing
CSRF-protected browser/service flows. They need separate API contracts because
checkout is session- and provider-bound, not a safe generic JSON write.

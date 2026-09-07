# Phase 12: Security implementation

## Controls added

- Browser responses use a nonce-based Content Security Policy. It permits only same-origin resources and the existing Chart.js CDN; inline script and style execution is disallowed.
- Security headers include frame denial, content-type sniffing protection, same-origin referrers, an isolated browser opener, and disabled camera, microphone, geolocation, and payment browser permissions.
- HTTPS redirects and secure cookies default on whenever `DJANGO_DEBUG=false`. HSTS remains disabled until the deployed HTTPS hostname is verified; enable it with `DJANGO_HSTS_SECONDS` after that point.
- Repeated failed login attempts are temporarily locked by email identifier or direct client IP. The current configurable threshold is five failures in 15 minutes, and each lockout creates a high-severity security event.
- Product images and avatars accept only GIF, JPEG, PNG, or WebP files up to 5 MB. Support attachments additionally allow PDF and text files.

## Deployment values

Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_CSRF_TRUSTED_ORIGINS` in the production environment. Set `DJANGO_TRUST_PROXY_HEADERS=true` only behind the controlled reverse proxy configured in Phase 17. Do not enable HSTS until HTTPS works for the primary domain and every required subdomain.

## Existing protections retained

Django CSRF middleware, ORM parameterization, password validators and hashing, server-side permissions, MFA secret encryption, signed email/reset tokens, webhook signature validation, and append-only security/audit records remain the authoritative controls. Payment webhooks are the only CSRF-exempt server endpoints, and each verifies its provider signature before changing state.

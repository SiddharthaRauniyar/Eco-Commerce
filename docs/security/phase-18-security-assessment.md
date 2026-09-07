# Phase 18 — Security Assessment

## Assessment boundary

This is an evidence-based review of the application code, settings, and
automated checks. It is not a penetration test, a production monitoring
exercise, or a compliance certification. The safe assurance workspace remains
non-exploiting by design; it checks defensive configuration and validation but
does not generate attack payloads or scan external systems.

## Controls confirmed in code

| Area | Implemented control | Verification evidence |
| --- | --- | --- |
| Authentication | Email-first custom user model, verification before activation, reset tokens, TOTP MFA, password validators, and session expiry choice | `apps.accounts.tests.AuthenticationFlowTests` |
| Brute-force resistance | Failed attempts are recorded; the configurable email/IP threshold creates a lockout and security event | `apps.security.tests.SecurityImplementationTests` and API MFA/lockout test |
| Authorization | Django permissions gate staff, analyst, customer-owned order, wishlist, address, and API resources | Dashboard, security, API, and order tests |
| Browser protection | CSRF middleware, nonce-based CSP, frame denial, no-sniff, referrer, permissions, and opener policies | Security header test and assurance module |
| Input and uploads | Django ORM querysets, form validation, and shared allow-list/content/size checks for images and support uploads | Upload negative test; safe raw-query reference check |
| Payments | Provider webhooks are the only CSRF-exempt paths; Stripe signatures are time-bound and constant-time compared; payment changes are idempotent and transactional | `apps.payments.tests.PaymentFlowTests` |
| Inventory and orders | Locking/transactions protect stock adjustment, checkout, payment completion, cancellation, and refunds | Cart, product, order, and payment tests |
| Audit and monitoring | Login attempts, activity/audit logs, security events, permission-controlled monitoring, and audited resolution actions | Security monitoring tests |
| Deployment | Production settings fail closed for placeholder secrets/hosts, database, Redis, proxy trust, mail delivery, and invalid MFA keys; Nginx keeps application/database services private | Production settings check and Compose validation |
| Recovery | Custom-format PostgreSQL dump, archive validation, bounded retention, documented restore drill, and offsite-copy requirement | `infra/backup-postgres.sh` and Phase 17 runbook |

## Test evidence

The final local regression run completed **52 Django tests** successfully:

```sh
python3 manage.py test --verbosity 1
python3 manage.py check
python3 manage.py makemigrations --check --dry-run
python3 -m pip check
```

The production settings profile also passed `manage.py check --deploy` using
real-shaped, non-secret environment values. Compose renders for both the main
and maintenance profiles. See [Phase 18 testing](../testing/phase-18-testing.md)
for the full execution and acceptance record.

## Residual risks and release actions

1. Configure the external TLS terminator before public traffic. It must pass
   the HTTPS scheme header, and Nginx's real-IP configuration must trust only
   the terminator's known address range.
2. Keep HSTS disabled until all required hostnames work over HTTPS; only then
   raise its duration, add subdomains, and consider preload.
3. Supply real SMTP and payment-provider credentials, verify provider webhook
   endpoints in their sandbox, then repeat the checkout tests against the
   live integration. No real provider transaction was run in this repository.
4. Run the Compose stack on the deployment host and perform the documented
   backup-and-restore drill. The local Docker daemon was unavailable during
   this assessment, so no live container smoke test was claimed.
5. Replicate encrypted database backups offsite, restrict access to `.env`,
   and alert on failed backup jobs.
6. Add dependency, container-image, and infrastructure scanning to the CI/CD
   environment before release; no external scanner result is represented here.

## Release decision

The codebase is ready for a controlled staging deployment once the release
actions above are completed. Production launch should be gated on a real TLS
check, SMTP/provider webhook smoke tests, and a successful restore drill.

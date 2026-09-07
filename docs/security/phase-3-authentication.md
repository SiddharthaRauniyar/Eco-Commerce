# Phase 3 — Authentication, MFA, and RBAC

## Delivered authentication flow

1. A visitor registers with an email address and a validated password.
2. The account is stored as inactive and receives a signed, time-limited email
   verification link. The registration response never logs the user in.
3. Verification marks the email as verified, activates the account, creates a
   profile if necessary, and invalidates the used link.
4. A verified user signs in with email and password. A successful password is
   not sufficient when MFA is enabled: only a short-lived pending-session value
   is recorded until the six-digit TOTP check succeeds.
5. The completed login cycles Django's session, records the outcome in
   `LoginAttempt`, and uses a browser-session expiry by default or a 14-day
   expiry when the user selects “remember me”.
6. Password resets use Django's signed, one-time reset tokens. The reset view
   produces the same generic success page for matching and non-matching emails.

## Routes

| Route | Purpose | Access |
| --- | --- | --- |
| `/accounts/register/` | Register a pending account | Public |
| `/accounts/verify/<uid>/<token>/` | Verify email and activate account | Public, signed link |
| `/accounts/verification/resend/` | Resend a verification link | Public, enumeration-safe response |
| `/accounts/login/` and `/accounts/logout/` | Browser session authentication | Public / authenticated POST |
| `/accounts/password-reset/` | Start and complete a password reset | Public, signed one-time link |
| `/accounts/mfa/setup/` | Enrol a TOTP authenticator | Authenticated |
| `/accounts/mfa/challenge/` | Complete a pending MFA login | Pending password login only |
| `/accounts/mfa/disable/` | Remove MFA after password confirmation | Authenticated |
| `/accounts/profile/` | Minimal authenticated account landing page | Authenticated |

## MFA design

- TOTP follows RFC 6238's standard HMAC-based six-digit flow with 30-second
  intervals and one interval of clock-skew tolerance.
- The secret is generated with `secrets.token_bytes`, displayed only while the
  user enrols it, then stored in `UserProfile.mfa_secret_encrypted` with
  `cryptography.fernet.Fernet`.
- `MFA_ENCRYPTION_KEY` must be a stable Fernet key in every deployed
  environment. Local development derives a temporary key from
  `DJANGO_SECRET_KEY` so the app remains runnable without checked-in secrets.
- A failed MFA code does not create an authenticated session and is logged as a
  failed login attempt.

Generate a production key once and store it in the deployment secret manager:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Roles and permissions

The `seed_roles` management command creates these groups using Django's native
model permissions:

| Role | Permission scope |
| --- | --- |
| Customer | Self-service access is enforced by object ownership in future services; no staff model permissions. |
| Support Agent | Support-ticket updates and order viewing. |
| Catalog Manager | Categories, products, and review moderation. |
| Order Manager | Orders, payment status, and coupon viewing. |
| Marketing Manager | Coupons, blog content, and notifications. |
| Analyst | Read-only order, product, and review data. |
| Security Analyst | Security events, activity/audit logs, login attempts, and vulnerability reports. |
| Administrator | All application model permissions. |

Run this after migrations and whenever a new model permission is introduced:

```bash
python manage.py seed_roles
```

Staff route implementations use `role_required("Role name")`. This rejects a
logged-in user without an approved group and permits a Django superuser for
break-glass recovery.

## Security configuration required for deployment

| Setting | Development default | Production requirement |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | temporary local value | unique secret from a secret store |
| `MFA_ENCRYPTION_KEY` | derived only for local development | stable Fernet key from a secret store |
| `DJANGO_EMAIL_BACKEND` | console mail backend | authenticated transactional-email backend |
| `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT` | blank / `587` | SMTP provider hostname and port |
| `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD` | blank | SMTP credentials from a secret store |
| `DJANGO_EMAIL_USE_TLS` | `true` | `true` unless the email provider specifies otherwise |
| `DEFAULT_FROM_EMAIL` | local placeholder | verified sending address |
| `DJANGO_ALLOWED_HOSTS` | empty with `DEBUG=true` | explicit public host names |

HTTPS, HSTS, CSP, rate limiting, account lockout, security headers, and the
reverse-proxy configuration are intentionally implemented in the dedicated
security and deployment phases. They are not simulated with insecure stubs.

## Verification performed

- `python manage.py check`
- `python manage.py makemigrations --check --dry-run`
- `python manage.py test` — five tests pass
- Python compilation and Git whitespace checks

The tests cover pending registration and email activation, MFA-gated sign-in,
password-reset email delivery, RBAC group synchronization, and the Phase 2
order snapshot relationship.

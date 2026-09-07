# Phase 17 — Deployment preparation

## Production stack

The production Compose stack runs PostgreSQL, Redis, the Django application
under Gunicorn, and Nginx. PostgreSQL and Redis are internal-only services;
Nginx is the only HTTP-facing container and is bound to `127.0.0.1:8080`.
Put a controlled TLS terminator in front of it. That terminator must send
`X-Forwarded-Proto: https` before traffic reaches Nginx, or Nginx must be
given an equivalent TLS configuration before the site is exposed publicly.

`DJANGO_TRUST_PROXY_HEADERS=true` is safe here because the Django `web`
container has no published port and Nginx overwrites `X-Real-IP` before the
request reaches it. If an upstream TLS proxy supplies a client IP through
`X-Forwarded-For`, configure Nginx's `realip` module with only that proxy's
known IP/CIDR so `$remote_addr` is normalized before Nginx forwards it. Never
expose `web` directly or blindly trust a browser-supplied `X-Forwarded-For`.

1. Copy `.env.example` to `.env` and replace every placeholder secret.
2. Set the real public hostnames in `DJANGO_ALLOWED_HOSTS` and their HTTPS
   origins in `DJANGO_CSRF_TRUSTED_ORIGINS`.
3. Keep `.env` out of source control and restrict its filesystem permissions.
   Use a URL-safe `REDIS_PASSWORD` or percent-encode it in `REDIS_URL`.
4. Enable HSTS only after HTTPS works for every required hostname. Add
   subdomains and preload only after verifying that every current and future
   subdomain is HTTPS-only.
5. From the project directory, start the stack with:

   ```sh
   docker compose up --build -d
   ```

The web container applies migrations and collects static files before Gunicorn
starts. Check its output with `docker compose logs -f web`; only point DNS or a
load balancer at Nginx after the health endpoint is healthy.

Generate an independent MFA encryption key before enabling MFA:

```sh
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

## Database backups

The `backup` Compose service is intentionally an on-demand maintenance job,
not a second long-running application. It uses the PostgreSQL client tools in
its container to write a timestamped custom-format dump to the `backup_data`
volume:

```sh
docker compose --profile maintenance run --rm backup
```

`infra/backup-postgres.sh` requires `POSTGRES_HOST`, `POSTGRES_DB`,
`POSTGRES_USER`, and `POSTGRES_PASSWORD`. It accepts `POSTGRES_PORT` (default
`5432`), `BACKUP_DIR` (default `/backups`), and `BACKUP_RETENTION_DAYS`
(default `14`). It refuses missing or invalid configuration, validates each
dump with `pg_restore --list`, writes files with owner-only permissions, and
deletes only files matching its own `secure-commerce-YYYYMMDDTHHMMSSZ.dump`
naming pattern.

Schedule the same command once per day from the deployment host after testing
one manual backup. For example, add this to the service account's crontab,
adjusting the checkout location and Docker path if needed:

```cron
0 2 * * * cd /srv/secure-commerce && /usr/local/bin/docker compose --profile maintenance run --rm backup >> /var/log/secure-commerce-backup.log 2>&1
```

Ensure the cron user can run Docker and write its log. Monitor that log and
alert when a scheduled run fails; a scheduler alone does not prove that a
backup can be restored.

## Restore drill

Choose a maintenance window, stop writes, and copy the selected dump out of
the backup volume or into the database container. Restore into the intended
database only:

```sh
docker compose exec -T db sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore --exit-on-error --clean --if-exists --no-owner --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' < secure-commerce-YYYYMMDDTHHMMSSZ.dump
```

Run a restore drill against a non-production PostgreSQL database first. The
local Docker volume is not offsite disaster recovery: replicate encrypted
backups to controlled, geographically separate storage and test that recovery
path regularly.

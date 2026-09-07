#!/bin/sh
# Create a PostgreSQL custom-format backup inside the maintenance container.
set -eu

: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

POSTGRES_PORT="${POSTGRES_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

case "$POSTGRES_PORT" in
    *[!0-9]* | "") echo "POSTGRES_PORT must be a number." >&2; exit 2 ;;
esac
case "$BACKUP_RETENTION_DAYS" in
    *[!0-9]* | "") echo "BACKUP_RETENTION_DAYS must be a non-negative number." >&2; exit 2 ;;
esac
case "$BACKUP_DIR" in
    /*) ;;
    *) echo "BACKUP_DIR must be an absolute path." >&2; exit 2 ;;
esac

command -v pg_dump >/dev/null 2>&1 || {
    echo "pg_dump is not available in this container." >&2
    exit 127
}
command -v pg_restore >/dev/null 2>&1 || {
    echo "pg_restore is not available in this container." >&2
    exit 127
}

umask 077
mkdir -p "$BACKUP_DIR"
[ -w "$BACKUP_DIR" ] || {
    echo "Backup directory is not writable: $BACKUP_DIR" >&2
    exit 1
}

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="$BACKUP_DIR/secure-commerce-$timestamp.dump"
[ ! -e "$backup_file" ] || {
    echo "Refusing to overwrite existing backup: $backup_file" >&2
    exit 1
}

temporary_file="$(mktemp "$BACKUP_DIR/.secure-commerce-backup.XXXXXX")"
cleanup() {
    rm -f "$temporary_file"
}
trap cleanup 0
trap 'cleanup; exit 1' HUP INT TERM

export PGPASSWORD="$POSTGRES_PASSWORD"
export PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
pg_dump \
    --host="$POSTGRES_HOST" \
    --port="$POSTGRES_PORT" \
    --username="$POSTGRES_USER" \
    --format=custom \
    --file="$temporary_file" \
    "$POSTGRES_DB"
pg_restore --list "$temporary_file" >/dev/null
mv "$temporary_file" "$backup_file"
trap - 0 HUP INT TERM

find "$BACKUP_DIR" -maxdepth 1 -type f \
    -name 'secure-commerce-[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9][0-9][0-9]Z.dump' \
    -mtime "+$BACKUP_RETENTION_DAYS" \
    -delete

printf 'Created backup: %s\n' "$backup_file"

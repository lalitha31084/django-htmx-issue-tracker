#!/bin/sh
# ==============================================================================
# Container entrypoint.
#
#   1. wait for PostgreSQL to accept connections
#   2. apply migrations - the data migration also seeds the demo content
#   3. run the seeding command again as a safety net (idempotent)
#   4. hand over to the process in CMD (Gunicorn by default)
#
# Written for POSIX /bin/sh (Alpine-compatible, no bashisms) and made
# idempotent so `docker compose restart` is safe.
# ==============================================================================

set -eu

log() {
    echo "[entrypoint] $*"
}

# --------------------------------------------------------------------------
# 1. Wait for the database
# --------------------------------------------------------------------------
wait_for_database() {
    attempts="${DB_WAIT_ATTEMPTS:-30}"
    delay="${DB_WAIT_INTERVAL:-2}"
    host="${POSTGRES_HOST:-db}"
    port="${POSTGRES_PORT:-5432}"
    log="Waiting up to ${attempts}x${delay}s for PostgreSQL at ${host}:${port} ..."

    i=1
    while [ "$i" -le "$attempts" ]; do
        if python manage.py check --database default >/dev/null 2>&1; then
            log "PostgreSQL is accepting connections."
            return 0
        fi
        i=$((i + 1))
        sleep "$delay"
    done

    log "ERROR: PostgreSQL did not become available in time."
    log "Check that the 'db' service is running and POSTGRES_* variables match."
    return 1
}

# --------------------------------------------------------------------------
# 2/3. Prepare the database schema and demo data
# --------------------------------------------------------------------------
prepare_database() {
    log "Applying database migrations (this also seeds the demo data)..."
    python manage.py migrate --noinput

    log "Ensuring demo data exists..."
    python manage.py seed_demo_data

    log "Collecting static files..."
    python manage.py collectstatic --noinput --clear >/dev/null 2>&1 \
        || log "collectstatic skipped (already collected or read-only)."

    if [ "${CREATE_SUPERUSER:-False}" = "True" ]; then
        log "Ensuring a superuser exists (${DJANGO_SUPERUSER_USERNAME:-admin})..."
        python manage.py createsuperuser --noinput 2>/dev/null \
            || log "Superuser already present."
    fi
}

main() {
    log "Starting $(basename "$0") ..."
    wait_for_database
    prepare_database

    log "Collecting startup arguments: $*"
    exec "$@"
}

main "$@"
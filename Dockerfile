# syntax=docker/dockerfile:1
# ==============================================================================
# Multi-stage Dockerfile for the progressively enhanced issue tracker.
#
#   stage 1 (builder)  - installs the Python dependencies into a virtualenv
#   stage 2 (runtime)  - slim image running Gunicorn as a non-root user
#
# Multi-stage keeps compilers and build caches out of the final image, which
# makes it considerably smaller and removes build tooling from production.
# ==============================================================================

# ---------------------------------------------------------------- builder ---
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build tools are only needed while compiling any dependency that has no wheel.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies first so the layer is cached across code changes.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip && pip install -r /tmp/requirements.txt

# --------------------------------------------------------------- runtime ---
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings

# libpq5 is the PostgreSQL client library psycopg links against; curl is used
# by the container healthcheck.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy the application code.
COPY . /app

# Collect static files into STATIC_ROOT at build time so the runtime image can
# serve them straight from disk via WhiteNoise.
RUN DJANGO_SECRET_KEY=build-only-key python manage.py collectstatic --noinput

# Entrypoint waits for PostgreSQL, applies migrations (which also seeds the demo
# data) and finally execs the server.
RUN chmod +x /app/scripts/entrypoint.sh \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=5 \
    CMD curl -fsS http://localhost:8000/health/ || exit 1

# Invoked through `sh` explicitly so the container does not depend on the
# executable bit being preserved by git or by a bind mount.
ENTRYPOINT ["sh", "/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--threads", "2", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
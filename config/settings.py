"""Django settings for the progressively enhanced issue tracker.

All configuration is driven by environment variables so the exact same image can
run locally, in Docker Compose and in production. See ``.env.example`` for the
full list of supported variables.
"""

from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma separated environment variable into a list."""
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core security settings
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-development-key-do-not-use-in-production")

DEBUG = env_bool("DEBUG", False)

# Comma separated list, e.g. "localhost,127.0.0.1".
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "*")

# Comma separated list of origins allowed to send unsafe (POST/PUT/DELETE)
# cross-origin requests. HTMX only needs this when a front-end is served from a
# different origin than the API.
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "tracker",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# WhiteNoise serves collected static files (CSS/JS) straight from the
# application container, which is all that is needed for a single-container
# deployment. It is enabled automatically whenever the package is installed.
if env_bool("USE_WHITENOISE", True):
    try:
        import whitenoise  # noqa: F401

        MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
        WHITENOISE_AUTOREFRESH = DEBUG
    except ImportError:  # pragma: no cover - optional dependency
        pass

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.app_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# PostgreSQL is the target database (see docker-compose.yml). Individual
# connection settings are read from ``POSTGRES_*`` variables. If
# ``USE_SQLITE`` is enabled the project falls back to a local SQLite file which
# keeps the test suite runnable without a database server.

if env_bool("USE_SQLITE", False):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", "issue_tracker"),
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.getenv("POSTGRES_HOST", "db"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": int(os.getenv("POSTGRES_CONN_MAX_AGE", "60")),
            "OPTIONS": {"connect_timeout": int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "10"))},
            "TEST": {"NAME": os.getenv("POSTGRES_TEST_DB", "test_issue_tracker")},
        }
    }

# ``DATABASE_URL`` is accepted for platforms that inject a single connection
# string (Heroku style). When present it takes precedence and is parsed into the
# individual ``DATABASES["default"]`` keys.
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    from urllib.parse import unquote, urlparse

    parsed = urlparse(DATABASE_URL)
    DATABASES["default"].update(
        {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")) or "issue_tracker",
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "db",
            "PORT": str(parsed.port or 5432),
        }
    )


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "project_list"
LOGOUT_REDIRECT_URL = "project_list"


# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# Serve uploaded/static files from the application process during development.
# In production a reverse proxy or object store should take over.
if env_bool("SERVE_STATIC", True):
    pass  # static files handled by WhiteNoise when installed

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Security (only enforced when DEBUG is off)
# ---------------------------------------------------------------------------

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", False)
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", False)
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    CSRF_COOKIE_HTTPONLY = False  # the HTMX bundle needs to read the CSRF token


# ---------------------------------------------------------------------------
# Application specific settings
# ---------------------------------------------------------------------------

# Names of the enhancement headers checked by the views. HTMX sends
# ``HX-Request``; plain ``fetch()`` based fallbacks can send ``X-Requested-With``.
HTMX_REQUEST_HEADER = "HX-Request"
AJAX_REQUEST_HEADER = "X-Requested-With"

# Log every HTMX interaction at INFO level to make progressive enhancement easy
# to debug from the container logs.
LOG_HTMX_REQUESTS = env_bool("LOG_HTMX_REQUESTS", True)

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{levelname}] {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
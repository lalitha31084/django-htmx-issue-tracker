# Progressively Enhanced Issue Tracker

A server-rendered issue tracker built with **Django** and progressively enhanced with **HTMX** for a modern, dynamic user experience — without sacrificing the no-JavaScript baseline.

## Table of Contents

- [Overview](#overview)
- [Architecture & Design Decisions](#architecture--design-decisions)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
  - [Quick Start (Docker)](#quick-start-docker)
  - [Local Development (without Docker)](#local-development-without-docker)
- [Project Structure](#project-structure)
- [Data Model](#data-model)
- [URL Endpoints](#url-endpoints)
- [Progressive Enhancement Strategy](#progressive-enhancement-strategy)
- [Testing](#testing)
- [Environment Variables](#environment-variables)

---

## Overview

This project implements a complete web application for tracking issues within software projects. The core architectural principle is **progressive enhancement**: the application is fully functional with JavaScript disabled (pure server-side rendering), and then layers on HTMX-powered dynamic behaviour for users whose browsers support it.

Every mutating action (create issue, update status, add comment) works in two modes:

| Mode | How it works | Response |
|------|-------------|----------|
| **Standard (no JS)** | Normal `<form>` POST submission | `302` redirect → full page reload |
| **Enhanced (HTMX)** | AJAX POST with `HX-Request: true` header | `200` with an HTML fragment swapped into the DOM |

This means the application never breaks if a script fails to load, works with screen readers, and is fully crawlable by search engines.

---

## Architecture & Design Decisions

### 1. Server-Side Header Detection

The Django views inspect the incoming `HX-Request` header (or `X-Requested-With: XMLHttpRequest` for vanilla `fetch()` clients) to decide whether to return a full page or an HTML fragment. This logic is centralised in [`tracker/http.py`](tracker/http.py) via the `is_enhanced_request()` helper, keeping the views declarative and DRY.

### 2. Partial Templates

Templates are structured for reuse:

- **Full-page templates** (e.g., `project_board.html`) extend `base.html` and `{% include %}` partial templates.
- **Partial templates** (e.g., `partials/_issue_card.html`, `partials/_comment.html`) render a single component and are used by both the full page and the enhanced fragment response.

This means the same HTML is served whether the page loads fresh or a fragment is swapped in by HTMX — zero duplication.

### 3. Service Layer

Business logic lives in [`tracker/services.py`](tracker/services.py), keeping views thin. The service functions are independently testable and use `@transaction.atomic` for data integrity.

### 4. Forms for Validation

All user input goes through Django `ModelForm` classes ([`tracker/forms.py`](tracker/forms.py)). The same form classes are bound to both the plain HTML `<form>` and the HTMX `hx-post` attributes, so validation is identical regardless of JavaScript availability.

### 5. No SPA Framework

Instead of React/Vue/Angular, interactivity is provided by HTMX attributes directly on HTML elements. This keeps the rendering logic, state management, and business logic on the server, drastically simplifying the architecture.

---

## Technology Stack

| Tool | Purpose |
|------|---------|
| **Python 3.12** | Language runtime |
| **Django 5.x** | Web framework (SSR, ORM, forms, templates) |
| **HTMX** | Progressive enhancement (dynamic DOM updates via HTML attributes) |
| **PostgreSQL 16** | Production database |
| **Docker & Docker Compose** | Containerised development and deployment |
| **Gunicorn** | Production-grade WSGI server |

---

## Getting Started

### Quick Start (Docker)

```bash
# 1. Clone the repository
git clone <repository-url>
cd django-htmx-issue-tracker

# 2. Copy the environment file (optional — defaults are provided)
cp .env.example .env

# 3. Build and start all services
docker compose up --build -d

# 4. Verify both services are healthy
docker compose ps
# Both 'web' and 'db' should show 'healthy' status

# 5. Open the application
# http://localhost:8000
```

The entrypoint script automatically:
1. Waits for PostgreSQL to be ready
2. Applies database migrations
3. Seeds the database with demo projects and issues
4. Collects static files
5. Starts Gunicorn

### Local Development (without Docker)

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Use SQLite for local development
export USE_SQLITE=True    # On Windows: set USE_SQLITE=True

# 4. Apply migrations
python manage.py migrate

# 5. Seed demo data
python manage.py seed_demo_data

# 6. Run the development server
python manage.py runserver
```

---

## Project Structure

```
django-htmx-issue-tracker/
├── config/                     # Django project configuration
│   ├── settings.py             # Settings (env-driven)
│   ├── urls.py                 # Root URL configuration
│   ├── wsgi.py                 # WSGI entry point
│   └── context_processors.py   # Template context processors
├── tracker/                    # Main application
│   ├── models.py               # Project, Issue, Comment models
│   ├── views.py                # View functions (SSR + fragment responses)
│   ├── forms.py                # Django ModelForms
│   ├── services.py             # Business logic / service layer
│   ├── http.py                 # Enhancement detection helpers
│   ├── admin.py                # Django admin registration
│   ├── templatetags/           # Custom template tags
│   ├── management/commands/    # Management commands (seed_demo_data)
│   ├── migrations/             # Database migrations (incl. data seeding)
│   └── tests/                  # Test suite
│       ├── base.py             # Shared test fixtures and assertions
│       ├── test_standard_requests.py   # No-JS baseline tests
│       ├── test_enhanced_requests.py   # HTMX / enhanced request tests
│       ├── test_models.py      # Model & form unit tests
│       └── test_http.py        # HTTP helper & endpoint tests
├── templates/
│   ├── base.html               # Base template (HTML shell)
│   ├── tracker/                # Full-page templates
│   │   ├── project_list.html
│   │   ├── project_board.html
│   │   ├── issue_detail.html
│   │   └── ...
│   └── partials/               # Reusable HTML fragments
│       ├── _issue_card.html
│       ├── _issue_column.html
│       ├── _comment.html
│       ├── _comment_form.html
│       └── _issue_form.html
├── static/css/                 # Application styles
├── scripts/entrypoint.sh       # Docker container entrypoint
├── Dockerfile                  # Multi-stage Docker build
├── docker-compose.yml          # Two-service stack (web + db)
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variable documentation
└── README.md                   # This file
```

---

## Data Model

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────┐
│   Project    │       │      Issue       │       │   Comment    │
├──────────────┤       ├──────────────────┤       ├──────────────┤
│ id  (PK)     │       │ id  (PK)         │       │ id  (PK)     │
│ name         │◄──────│ project_id  (FK)  │       │ issue_id (FK)│──────►│
│ description  │  1:N  │ title            │  1:N  │ content      │
│ created_at   │       │ description      │◄──────│ created_at   │
└──────────────┘       │ status           │       └──────────────┘
                       │ created_at       │
                       │ updated_at       │
                       └──────────────────┘
```

**Status choices:** `To Do` · `In Progress` · `Done`

---

## URL Endpoints

| Method | URL | Purpose | Standard Response | Enhanced Response |
|--------|-----|---------|-------------------|-------------------|
| `GET` | `/` | Dashboard | Full page | — |
| `GET` | `/projects/` | List all projects | Full page | — |
| `GET` | `/projects/<id>/` | Issue board (grouped by status) | Full page | — |
| `POST` | `/projects/<id>/issues/create/` | Create a new issue | `302` → board | `200` + column fragment |
| `GET` | `/issues/<id>/` | Issue detail + comments | Full page | — |
| `POST` | `/issues/<id>/update-status/` | Update issue status | `302` → board | `200` + card fragment |
| `POST` | `/issues/<id>/comments/add/` | Add a comment | `302` → issue | `200` + comment fragment |
| `POST` | `/issues/<id>/delete/` | Delete an issue | `302` → board | `200` + notice fragment |
| `GET` | `/health/` | Liveness probe | JSON `{"status": "ok"}` | — |
| `GET` | `/health/db/` | Readiness probe (checks DB) | JSON `{"database": "ok"}` | — |

---

## Progressive Enhancement Strategy

### How It Works

```
User clicks "Move to Done"
         │
         ▼
┌─────────────────────┐
│   Browser sends     │
│   POST request      │
│   (with/without     │
│   HX-Request header)│
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Django View       │
│   checks headers    │
│   via is_enhanced() │
└────────┬────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
 No Header  HX-Request: true
    │         │
    ▼         ▼
 302 redirect   200 + HTML fragment
 (full reload)  (HTMX swaps into DOM)
```

### Key Implementation Details

1. **Header detection** (`tracker/http.py`): The `is_enhanced_request()` function checks for `HX-Request`, `X-Requested-With`, `HX-Boosted`, `Sec-Fetch-Dest`, and Accept header hints — making it work with HTMX, vanilla `fetch()`, jQuery, and Turbo.

2. **View branching** (`tracker/views.py`): Each mutating view returns either a redirect (standard) or a rendered partial (enhanced):

   ```python
   if is_enhanced_request(request):
       return render(request, 'partials/_issue_card.html', {'issue': issue})
   return redirect('project_board', project_id=issue.project_id)
   ```

3. **Template attributes** (HTML): HTMX attributes are layered onto standard forms:

   ```html
   <form method="post" action="{% url 'issue_update_status' issue.id %}"
         hx-post="{% url 'issue_update_status' issue.id %}"
         hx-target="#issue-{{ issue.id }}"
         hx-swap="outerHTML">
   ```

   Without JavaScript, the `<form>` submits normally. With HTMX loaded, the `hx-*` attributes intercept the submission and swap the response fragment.

---

## Testing

The test suite (**81 tests**) validates both request modes comprehensively:

```bash
# Run with SQLite (no database server required)
USE_SQLITE=True python manage.py test tracker -v2

# Run with Docker
docker compose exec web python manage.py test tracker -v2
```

### Test Organisation

| Module | What it covers |
|--------|---------------|
| `test_standard_requests.py` | No-JS baseline: full pages (200), redirects (302), form validation |
| `test_enhanced_requests.py` | HTMX mode: fragment responses (200), no `<html>` tags, header detection |
| `test_models.py` | Model validation, form logic, template tags |
| `test_http.py` | `is_enhanced_request()` helper, health endpoints, URL wiring |

### Example: Testing Both Modes

```python
# Standard request → 302 redirect
response = self.client.post(url, {"status": "Done"})
self.assertEqual(response.status_code, 302)

# Enhanced request → 200 with HTML fragment
response = self.client.post(url, {"status": "Done"}, HTTP_HX_REQUEST="true")
self.assertEqual(response.status_code, 200)
self.assertNotContains(response, "<html>")
self.assertTemplateUsed(response, "partials/_issue_card.html")
```

---

## Environment Variables

All configuration is driven by environment variables. See [`.env.example`](.env.example) for the full list with descriptions. Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | (insecure dev key) | Django secret key — **must change in production** |
| `DEBUG` | `False` | Enable debug mode |
| `ALLOWED_HOSTS` | `*` | Comma-separated allowed hostnames |
| `POSTGRES_DB` | `issue_tracker` | Database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | `postgres` | Database password |
| `DATABASE_URL` | (empty) | Single connection string (overrides individual vars) |
| `USE_SQLITE` | `False` | Use SQLite instead of PostgreSQL (for local dev/testing) |
| `WEB_PORT` | `8000` | Published port for the web service |

---

## License

This project was built as a learning exercise for progressive enhancement with Django and HTMX.

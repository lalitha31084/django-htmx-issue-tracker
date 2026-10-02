"""Views for the issue tracker.

Every mutating view follows the same contract:

===========================================  ============================  ===================
Request                                      Success (no JS)              Success (enhanced)
===========================================  ============================  ===================
``POST /projects/<id>/issues/create/``       ``302`` -> board             ``200`` + ``_issue_column.html``
``POST /issues/<id>/update-status/``         ``302`` -> board             ``200`` + ``_issue_card.html``
``POST /issues/<id>/comments/add/``          ``302`` -> issue detail      ``200`` + ``_comment.html``
``POST /issues/<id>/delete/``                ``302`` -> board             ``200`` + ``_empty_column.html``
``POST /comments/<id>/delete/``              ``302`` -> issue detail      ``200`` + ``_empty.html``
===========================================  ============================  ===================

Invalid input re-renders the corresponding form fragment with the bound errors
for enhanced clients and re-renders the full page for plain clients, so the
browser stays on the page either way.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import connection
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from . import services
from .forms import CommentForm, IssueForm, IssueStatusForm, ProjectForm
from .http import (
    htmx_only,
    is_enhanced_request,
    json_error,
    log_enhanced_request,
    wants_json,
)
from .models import Comment, Issue, Project

logger = logging.getLogger(__name__)

ISSUE_CARD_TEMPLATE = "partials/_issue_card.html"
ISSUE_COLUMN_TEMPLATE = "partials/_issue_column.html"
COMMENT_TEMPLATE = "partials/_comment.html"
EMPTY_TEMPLATE = "partials/_empty.html"


# ---------------------------------------------------------------------------
# Read-only pages
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "HEAD"])
def dashboard(request: HttpRequest) -> HttpResponse:
    """Landing page: overall statistics plus the most recent activity."""
    context = {
        "projects": services.project_list_queryset(),
        "recent_issues": services.recent_activity(),
        "status_choices": Issue.Status.choices,
        "total_issues": Issue.objects.count(),
        "open_issues": Issue.objects.exclude(status=Issue.Status.DONE).count(),
        "total_comments": services.total_comments(),
    }
    return render(request, "tracker/dashboard.html", context)


@require_http_methods(["GET", "HEAD"])
def project_list(request: HttpRequest) -> HttpResponse:
    """List every project."""
    return render(
        request,
        "tracker/project_list.html",
        {
            "projects": services.project_list_queryset(),
            "form": ProjectForm(),
        },
    )


@require_http_methods(["GET", "POST"])
def project_create(request: HttpRequest) -> HttpResponse:
    """Create a project.

    * No enhancement header -> ``302`` back to the project list.
    * ``HX-Request: true``   -> ``200`` with the refreshed project list.
    """
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = services.create_project(data=request.POST)
            log_enhanced_request("project_create", request, f" -> project {project.pk}")
            messages.success(request, f'Project "{project.name}" created.')
            if is_enhanced_request(request):
                return _render_fragment(
                    request,
                    "partials/_project_list.html",
                    {"projects": services.project_list_queryset(), "form": ProjectForm()},
                )
            return redirect("project_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProjectForm()

    if is_enhanced_request(request):
        return _render_fragment(
            request, "partials/_project_list.html", {"projects": services.project_list_queryset(), "form": form}
        )
    return render(request, "tracker/project_list.html", {"projects": services.project_list_queryset(), "form": form})


@require_http_methods(["GET", "HEAD"])
def project_board(request: HttpRequest, project_id: int) -> HttpResponse:
    """The issue board: all issues of ``project_id`` grouped by status.

    This page is the base layer of the project: it renders complete HTML and is
    fully usable with JavaScript disabled.
    """
    project = get_object_or_404(Project.objects.prefetch_related("issues"), pk=project_id)
    context = services.board_context(project)
    context["issue_form"] = IssueForm(project=project)
    return render(request, "tracker/project_board.html", context)


@require_http_methods(["GET", "POST"])
def project_edit(request: HttpRequest, project_id: int) -> HttpResponse:
    """Edit a project's name/description."""
    project = get_object_or_404(Project, pk=project_id)
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, f'Project "{project.name}" updated.')
            return redirect("project_board", project_id=project.pk)
    else:
        form = ProjectForm(instance=project)
    return render(request, "tracker/project_form.html", {"form": form, "project": project})


@require_http_methods(["GET", "HEAD"])
def issue_detail(request: HttpRequest, issue_id: int) -> HttpResponse:
    """Issue detail page with its description and comments."""
    issue = get_object_or_404(
        Issue.objects.select_related("project").prefetch_related("comments"), pk=issue_id
    )
    return render(
        request,
        "tracker/issue_detail.html",
        {
            "issue": issue,
            "project": issue.project,
            "comments": issue.comments.all(),
            "comment_form": CommentForm(issue=issue),
            "issue_form": IssueForm(instance=issue),
            "status_form": IssueStatusForm(initial={"status": issue.status}),
            "status_choices": Issue.Status.choices,
        },
    )


# ---------------------------------------------------------------------------
# Issue creation
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def issue_create(request: HttpRequest, project_id: int) -> HttpResponse:
    """Create an issue for a project.

    * ``GET``  - render the "new issue" form (full page or inline board form).
    * ``POST`` - ``302`` back to the board, or ``200`` with the refreshed board
      column so HTMX can swap it in place.
    """
    project = get_object_or_404(Project, pk=project_id)
    enhanced = is_enhanced_request(request)

    if request.method == "POST":
        form = IssueForm(request.POST, project=project)
        if form.is_valid():
            issue = form.save()
            log_enhanced_request("issue_create", request, f" -> issue {issue.pk}")
            messages.success(request, f'Issue "{issue.title}" created.')
            if enhanced:
                # Swap the whole (possibly changed) destination column so the new
                # card appears in its natural position.
                return _issue_column_response(request, project, issue.status)
            return redirect("project_board", project_id=project.pk)
        messages.error(request, "Please correct the errors below.")
    else:
        form = IssueForm(project=project)

    if enhanced:
        return _render_fragment(
            request,
            "partials/_issue_form.html",
            {"form": form, "project": project},
        )
    return render(
        request,
        "tracker/issue_form.html",
        {"form": form, "project": project, "issue": None},
    )


@require_http_methods(["GET", "POST"])
def issue_edit(request: HttpRequest, issue_id: int) -> HttpResponse:
    """Edit title/description of an existing issue."""
    issue = get_object_or_404(Issue, pk=issue_id)
    enhanced = is_enhanced_request(request)

    if request.method == "POST":
        form = IssueForm(request.POST, instance=issue)
        if form.is_valid():
            updated = form.save()
            log_enhanced_request("issue_edit", request, f" -> issue {updated.pk}")
            messages.success(request, f'Issue "{updated.title}" updated.')
            if enhanced:
                return _render_fragment(
                    request, ISSUE_CARD_TEMPLATE, {"issue": updated, "project": issue.project}
                )
            return redirect("issue_detail", issue_id=updated.pk)
        messages.error(request, "Please correct the errors below.")
    else:
        form = IssueForm(instance=issue)

    if enhanced:
        return _render_fragment(
            request, "partials/_issue_form.html", {"form": form, "issue": issue, "project": issue.project}
        )
    return render(
        request, "tracker/issue_form.html", {"form": form, "issue": issue, "project": issue.project}
    )


# ---------------------------------------------------------------------------
# Status updates - the flagship progressive enhancement
# ---------------------------------------------------------------------------


@require_POST
def update_issue_status(request: HttpRequest, issue_id: int) -> HttpResponse:
    """Move an issue to another board column.

    * No enhancement header -> ``302`` redirect to the project board.
    * ``HX-Request: true``   -> ``200`` with only ``partials/_issue_card.html``.
    """
    issue = get_object_or_404(Issue.objects.select_related("project"), pk=issue_id)
    form = IssueStatusForm(request.POST)

    if not form.is_valid():
        enhanced = is_enhanced_request(request)
        log_enhanced_request("update_issue_status", request, " (invalid)")
        if enhanced:
            return _render_fragment(
                request,
                ISSUE_CARD_TEMPLATE,
                {"issue": issue, "project": issue.project, "status_error": form.errors.get("status")},
                status=400,
            )
        messages.error(request, "Invalid status supplied.")
        return redirect("project_board", project_id=issue.project_id)

    issue = services.update_issue_status(issue=issue, status=form.cleaned_data["status"])
    log_enhanced_request("update_issue_status", request, f" -> {issue.status}")

    # A client that explicitly asks for JSON gets JSON, whether or not it also
    # sent an HTMX header.
    if wants_json(request):
        return JsonResponse({"ok": True, "issue_id": issue.pk, "status": issue.status})

    if is_enhanced_request(request):
        # Only the issue card is re-rendered; the HTMX attributes on it point at
        # the new column so the browser moves the card itself.
        return _render_fragment(request, ISSUE_CARD_TEMPLATE, {"issue": issue, "project": issue.project})

    messages.info(request, f'Issue "{issue.title}" moved to {issue.status}.')
    return redirect("project_board", project_id=issue.project_id)


@require_POST
@htmx_only
def update_issue_status_json(request: HttpRequest, issue_id: int) -> HttpResponse:
    """JSON variant of :func:`update_issue_status` for custom JS clients."""
    issue = get_object_or_404(Issue, pk=issue_id)
    form = IssueStatusForm(request.POST)
    if not form.is_valid():
        return json_error("; ".join(form.errors.get("status", [])), status=400)
    issue = services.update_issue_status(issue=issue, status=form.cleaned_data["status"])
    return JsonResponse(
        {
            "ok": True,
            "issue": {"id": issue.pk, "title": issue.title, "status": issue.status},
        }
    )


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@require_POST
def add_comment(request: HttpRequest, issue_id: int) -> HttpResponse:
    """Attach a comment to an issue.

    * No enhancement header -> ``302`` back to the issue detail page.
    * ``HX-Request: true``   -> ``200`` with only ``partials/_comment.html``.
    """
    issue = get_object_or_404(Issue.objects.select_related("project"), pk=issue_id)
    form = CommentForm(request.POST, issue=issue)
    enhanced = is_enhanced_request(request)

    if form.is_valid():
        comment = form.save()
        log_enhanced_request("add_comment", request, f" -> comment {comment.pk}")
        messages.success(request, "Comment added.")
        if wants_json(request):
            return JsonResponse({"ok": True, "comment_id": comment.pk})
        if enhanced:
            return _render_fragment(
                request,
                COMMENT_TEMPLATE,
                {"comment": comment, "issue": issue, "project": issue.project},
            )
        return redirect("issue_detail", issue_id=issue.pk)

    log_enhanced_request("add_comment", request, " (invalid)")
    messages.error(request, "A comment cannot be empty.")
    if enhanced:
        # Re-render just the form so the error appears next to the field. The
        # HTMX form targets itself, so the fragment lands in the right place.
        return _render_fragment(
            request,
            "partials/_comment_form.html",
            {"form": form, "issue": issue, "project": issue.project},
            status=400,
        )
    return redirect("issue_detail", issue_id=issue.pk)


@require_POST
def delete_comment(request: HttpRequest, comment_id: int) -> HttpResponse:
    """Delete a comment.

    * No enhancement header -> ``302`` back to the issue detail page.
    * ``HX-Request: true``   -> ``200`` with a small "comment removed" notice.
    """
    comment = get_object_or_404(Comment.objects.select_related("issue"), pk=comment_id)
    issue = services.delete_comment(comment=comment)
    log_enhanced_request("delete_comment", request, f" -> comment {comment_id}")

    if is_enhanced_request(request):
        return _render_fragment(
            request,
            EMPTY_TEMPLATE,
            {"message": "Comment deleted.", "issue": issue},
        )
    messages.info(request, "Comment deleted.")
    return redirect("issue_detail", issue_id=issue.pk)


# ---------------------------------------------------------------------------
# Deletion
# ---------------------------------------------------------------------------


@require_POST
def issue_delete(request: HttpRequest, issue_id: int) -> HttpResponse:
    """Delete an issue.

    * No enhancement header -> ``302`` to the project board.
    * ``HX-Request: true``   -> ``200`` with an "empty board" placeholder so the
      removed card's column can be updated.
    """
    issue = get_object_or_404(Issue.objects.select_related("project"), pk=issue_id)
    project = issue.project
    project_id = project.pk
    project_name = project.name
    title = issue.title
    services.delete_issue(issue=issue)
    log_enhanced_request("issue_delete", request, f" -> issue {issue_id}")

    if is_enhanced_request(request):
        return _render_fragment(
            request,
            EMPTY_TEMPLATE,
            {"message": f'Issue "{title}" deleted.', "project": project, "issue": None},
        )
    messages.info(request, f'Issue "{title}" deleted from {project_name}.')
    return redirect("project_board", project_id=project_id)


# ---------------------------------------------------------------------------
# Operational endpoints
# ---------------------------------------------------------------------------


@require_http_methods(["GET", "HEAD"])
def health(request: HttpRequest) -> HttpResponse:
    """Liveness probe - always ``200`` while Django can serve a request."""
    return JsonResponse({"status": "ok", "service": "issue-tracker"})


@require_http_methods(["GET", "HEAD"])
def health_db(request: HttpRequest) -> HttpResponse:
    """Readiness probe - ``200`` only when PostgreSQL answers a trivial query."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # pragma: no cover - only on a broken database
        logger.warning("database health check failed: %s", exc)
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _render_fragment(
    request: HttpRequest, template: str, context: dict, status: int = 200
) -> HttpResponse:
    """Render a partial and flag the response as an enhanced reply."""
    response = render(request, template, context, status=status)
    response["HX-Request"] = "true"
    response["Cache-Control"] = "no-store"
    return response


def _issue_column_response(request: HttpRequest, project: Project, status: str) -> HttpResponse:
    """Render the board column that holds issues with ``status``."""
    label = dict(Issue.Status.choices)[status]
    issues = project.issues.filter(status=status).order_by("id")
    column = {
        "value": status,
        "label": label,
        "slug": label.lower().replace(" ", "-"),
        "issues": issues,
        "count": issues.count(),
    }
    return _render_fragment(request, ISSUE_COLUMN_TEMPLATE, {"column": column, "project": project})


__all__ = [
    "add_comment",
    "delete_comment",
    "dashboard",
    "health",
    "health_db",
    "issue_create",
    "issue_delete",
    "issue_detail",
    "issue_edit",
    "project_board",
    "project_create",
    "project_edit",
    "project_list",
    "update_issue_status",
    "update_issue_status_json",
]
"""Thin service layer.

Business rules (validation, ordering, cascades) live here so the views stay
declarative and the rules can be unit tested without touching HTTP.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, QuerySet

from .forms import CommentForm, IssueForm, IssueStatusForm, ProjectForm
from .models import Comment, Issue, Project

__all__ = [
    "add_comment",
    "board_context",
    "create_issue",
    "create_project",
    "delete_comment",
    "delete_issue",
    "project_list_queryset",
    "recent_activity",
    "total_comments",
    "update_issue_status",
]


def project_list_queryset() -> QuerySet[Project]:
    """Projects annotated with issue counts so the list page needs one query."""
    return Project.objects.annotate(total_issues=Count("issues")).order_by("name", "id")


def board_context(project: Project) -> dict:
    """Build the context for the issue board in exactly two extra queries."""
    grouped = project.issues_by_status()
    status_counts = dict(
        project.issues.values_list("status").annotate(c=Count("id")).values_list("status", "c")
    )
    columns = [
        {
            "value": value,
            "label": label,
            "slug": label.lower().replace(" ", "-"),
            "issues": grouped.get(label),
            "count": status_counts.get(value, 0),
        }
        for value, label in Issue.Status.choices
    ]
    return {"project": project, "columns": columns}


def total_comments() -> int:
    """Total number of comments across every issue."""
    return Comment.objects.count()


def recent_activity(limit: int = 10) -> QuerySet[Issue]:
    """The most recently touched issues across all projects."""
    return (
        Issue.objects.select_related("project")
        .annotate(comment_total=Count("comments"))
        .order_by("-updated_at")[:limit]
    )


@transaction.atomic
def create_issue(*, project: Project, data: dict) -> Issue:
    """Create an issue from ``data``; raises ``ValidationError`` when invalid."""
    form = IssueForm(data, project=project)
    if not form.is_valid():
        raise ValidationError(form.errors)
    return form.save()


@transaction.atomic
def create_project(*, data: dict) -> Project:
    """Create a project; raises ``ValidationError`` when invalid."""
    form = ProjectForm(data)
    if not form.is_valid():
        raise ValidationError(form.errors)
    return form.save()


@transaction.atomic
def update_issue_status(*, issue: Issue, status: str) -> Issue:
    """Move ``issue`` to ``status``.

    Raises ``django.core.exceptions.ValidationError`` for unknown statuses.
    """
    form = IssueStatusForm({"status": status})
    if not form.is_valid():
        raise ValidationError(form.errors)
    issue.status = form.cleaned_data["status"]
    issue.save(update_fields=["status", "updated_at"])
    return issue


@transaction.atomic
def add_comment(*, issue: Issue, content: str) -> Comment:
    """Add a comment to ``issue``; raises ``ValidationError`` when empty."""
    form = CommentForm({"content": content}, issue=issue)
    if not form.is_valid():
        raise ValidationError(form.errors)
    return form.save()


@transaction.atomic
def delete_issue(*, issue: Issue) -> None:
    """Remove an issue (and, by cascade, its comments)."""
    issue.delete()


@transaction.atomic
def delete_comment(*, comment: Comment) -> Issue:
    """Remove a comment and return the issue it belonged to."""
    issue = comment.issue
    comment.delete()
    return issue
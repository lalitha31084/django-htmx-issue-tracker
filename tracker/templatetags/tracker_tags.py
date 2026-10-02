"""Template helpers used by the board and detail templates."""

from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="status_slug")
def status_slug(value: str) -> str:
    """``"In Progress"`` -> ``"in-progress"`` (used for CSS classes / anchors)."""
    return str(value).strip().lower().replace(" ", "-")


@register.filter(name="excerpt")
def excerpt(value: str, length: int = 140) -> str:
    """Trim ``value`` to ``length`` characters on a word boundary."""
    text = " ".join(str(value or "").split())
    if len(text) <= length:
        return text
    return text[: length - 1].rsplit(" ", 1)[0] + "…"


@register.simple_tag(name="next_status")
def next_status(issue) -> str:
    """Label of the status an issue would move to next."""
    value = issue.next_status
    return dict(type(issue).Status.choices).get(value, value)


@register.simple_tag(name="status_label")
def status_label(value: str) -> str:
    """Human readable label for a stored status value."""
    from tracker.models import Issue

    return dict(Issue.Status.choices).get(value, value)


@register.simple_tag(name="progress_percent")
def progress_percent(project) -> int:
    """Percentage of a project's issues that are ``Done`` (rounded)."""
    from tracker.models import Issue

    total = project.issue_count
    if not total:
        return 0
    done = project.issues.filter(status=Issue.Status.DONE).count()
    return int(round(done / total * 100))


@register.simple_tag(takes_context=True, name="query_string")
def query_string(context, **kwargs) -> str:
    """Rebuild the current query string with ``kwargs`` replaced."""
    request = context.get("request")
    params = request.GET.copy() if request else {}
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode() if hasattr(params, "urlencode") else params
    return f"?{encoded}" if encoded else ""


@register.simple_tag(name="status_badge")
def status_badge(value: str) -> str:
    """Render a small, dependency free status badge."""
    label = status_label(value)
    safe_label = conditional_escape(label)
    return mark_safe(
        f'<span class="badge badge--{status_slug(label)}">{safe_label}</span>'  # noqa: S308
    )
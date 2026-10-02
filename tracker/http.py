"""Helpers for detecting *enhanced* (AJAX / HTMX) requests.

The whole progressive-enhancement contract of this project lives in this one
module: every mutating view asks :func:`is_enhanced_request` whether it should
answer with a small HTML fragment or with a full page / redirect.
"""

from __future__ import annotations

import logging
from functools import wraps

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.cache import never_cache

logger = logging.getLogger(__name__)

#: Sent by HTMX on every request it issues.
HTMX_HEADER = getattr(settings, "HTMX_REQUEST_HEADER", "HX-Request")
#: Conventional header used by hand written ``fetch()`` based enhancements.
AJAX_HEADER = getattr(settings, "AJAX_REQUEST_HEADER", "X-Requested-With")
#: HTML forms submitted by HTMX cannot carry custom headers, but HTMX always
#: advertises itself through one of the headers below.
TRUTHY_VALUES = {"true", "1", "yes", "on"}


def is_enhanced_request(request: HttpRequest) -> bool:
    """Return ``True`` when the client can consume an HTML fragment.

    The check is deliberately liberal so that any reasonable enhancement layer
    (HTMX, ``fetch()``, jQuery, Turbo, ...) is detected:

    * ``HX-Request: true`` - set automatically by HTMX.
    * ``X-Requested-With: XMLHttpRequest`` - conventional AJAX marker.
    * ``HX-Boosted: true`` - HTMX boosting a normal link/form navigation.
    * ``Sec-Fetch-Dest: empty`` - sent by ``fetch()`` based partial updates.
    * ``Accept`` containing ``HX-Request`` - an explicit "fragments please" hint.
    """
    htmx = request.headers.get(HTMX_HEADER, "")
    if htmx and htmx.strip().lower() in TRUTHY_VALUES:
        return True

    ajax = request.headers.get(AJAX_HEADER, "")
    if ajax and ajax.strip().lower() in {"xmlhttprequest", "fetch", "true"}:
        return True

    boosted = request.headers.get("HX-Boosted", "")
    if boosted and boosted.strip().lower() in TRUTHY_VALUES:
        return True

    sec_fetch_dest = request.headers.get("Sec-Fetch-Dest", "")
    if sec_fetch_dest.strip().lower() == "empty":
        return True

    accept = request.headers.get("Accept", "")
    if HTMX_HEADER.lower() in accept.lower():
        return True

    return False


def htmx_target(request: HttpRequest, default: str = "") -> str:
    """Read the ``HX-Target`` header sent by HTMX (useful for error rendering)."""
    return request.headers.get("HX-Target", default)


def wants_json(request: HttpRequest) -> bool:
    """Return ``True`` when the client explicitly asked for a JSON payload.

    An ``HX-Request`` header always wins: HTMX consumes HTML fragments, so it
    never receives JSON even if its ``Accept`` header is unusual.
    """
    if request.headers.get(HTMX_HEADER, "").strip().lower() in TRUTHY_VALUES:
        return False
    accept = request.headers.get("Accept", "")
    return "application/json" in accept.lower()


def render_partial(request: HttpRequest, template: str, context: dict) -> HttpResponse:
    """Render an HTML fragment with the ``HX-Request`` response header set."""
    response = render(request, template, context)
    response[HTMX_HEADER] = "true"
    return response


def render(
    request: HttpRequest,
    template: str,
    context: dict,
    status: int = 200,
    content_type: str | None = None,
) -> HttpResponse:
    """Thin wrapper around :func:`django.shortcuts.render` with a sane status code."""
    from django.shortcuts import render as django_render

    return django_render(request, template, context, status=status, content_type=content_type)


def json_error(message: str, status: int = 400) -> HttpResponse:
    """Return a small JSON error payload for API-ish clients."""
    from django.http import JsonResponse

    return JsonResponse({"ok": False, "error": message}, status=status)


def log_enhanced_request(view_name: str, request: HttpRequest, extra: str = "") -> None:
    """Emit a single INFO line describing an enhanced interaction."""
    if getattr(settings, "LOG_HTMX_REQUESTS", False):
        logger.info(
            "htmx %s %s%s (Sec-Fetch-Dest=%s)",
            request.method,
            request.path,
            extra,
            request.headers.get("Sec-Fetch-Dest", "-"),
        )


def htmx_only(view_func):
    """Return ``409 Conflict`` when a view is called without enhancement headers.

    Used for endpoints that only make sense for an enhanced client (for example
    the JSON status endpoint) so that a plain browser request fails loudly
    instead of silently doing nothing.
    """

    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not is_enhanced_request(request):
            return json_error("This endpoint requires an enhanced (HX-Request) request.", status=409)
        return view_func(request, *args, **kwargs)

    return _wrapped


def fragment_response(view_func):
    """Decorator setting ``HX-Request: true`` and ``Cache-Control: no-store``.

    Fragment responses must never be cached, otherwise the browser (or a proxy)
    could replay a stale issue card.
    """

    @wraps(view_func)
    @never_cache
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        response = view_func(request, *args, **kwargs)
        response[HTMX_HEADER] = "true"
        response["Cache-Control"] = "no-store"
        return response

    return _wrapped
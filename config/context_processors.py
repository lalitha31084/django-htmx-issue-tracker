"""Custom template context processors for the project."""

from django.conf import settings


def app_settings(request):
    """Expose a small, explicit set of settings to every template.

    Templates cannot read ``django.conf.settings`` directly, so anything the
    templates need (currently only ``DEBUG``, used to switch on the verbose
    logging of the enhancement layer) has to be declared here.
    """
    return {
        "DEBUG": settings.DEBUG,
        "LOG_HTMX_REQUESTS": getattr(settings, "LOG_HTMX_REQUESTS", False),
    }
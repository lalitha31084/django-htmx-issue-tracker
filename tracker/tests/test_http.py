"""Operational endpoints, HTTP header helper and URL wiring."""

from __future__ import annotations

import json

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from tracker.http import is_enhanced_request
from tracker.models import Issue


class HealthEndpointTests(TestCase):
    def test_health_reports_ok(self) -> None:
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["status"], "ok")

    def test_database_health_reports_ok(self) -> None:
        response = self.client.get(reverse("health_db"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["database"], "ok")

    def test_health_accepts_head(self) -> None:
        self.assertEqual(self.client.head(reverse("health")).status_code, 200)


class IsEnhancedRequestTests(TestCase):
    """Unit tests for the header sniffing helper."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_plain_request_is_not_enhanced(self) -> None:
        self.assertFalse(is_enhanced_request(self.factory.post("/issues/1/update-status/")))

    def test_htmx_header_is_enhanced(self) -> None:
        request = self.factory.post("/", HTTP_HX_REQUEST="true")
        self.assertTrue(is_enhanced_request(request))

    def test_ajax_header_is_enhanced(self) -> None:
        request = self.factory.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertTrue(is_enhanced_request(request))

    def test_boosted_header_is_enhanced(self) -> None:
        self.assertTrue(is_enhanced_request(self.factory.get("/", HTTP_HX_BOOSTED="true")))

    def test_sec_fetch_dest_empty_is_enhanced(self) -> None:
        self.assertTrue(is_enhanced_request(self.factory.get("/", HTTP_SEC_FETCH_DEST="empty")))

    def test_accept_hint_is_enhanced(self) -> None:
        request = self.factory.get("/", HTTP_ACCEPT="text/html, HX-Request")
        self.assertTrue(is_enhanced_request(request))

    def test_falsey_values_are_not_enhanced(self) -> None:
        self.assertFalse(is_enhanced_request(self.factory.post("/", HTTP_HX_REQUEST="false")))
        self.assertFalse(is_enhanced_request(self.factory.post("/", HTTP_HX_BOOSTED="0")))


class UrlWiringTests(TestCase):
    """The specification pins exact URLs; make sure they resolve."""

    def test_specification_urls(self) -> None:
        self.assertEqual(reverse("project_board", args=[7]), "/projects/7/")
        self.assertEqual(reverse("issue_create", args=[7]), "/projects/7/issues/create/")
        self.assertEqual(reverse("issue_update_status", args=[3]), "/issues/3/update-status/")
        self.assertEqual(reverse("comment_add", args=[3]), "/issues/3/comments/add/")
        self.assertEqual(reverse("issue_detail", args=[3]), "/issues/3/")

    def test_project_board_route_pattern(self) -> None:
        self.assertEqual(self.client.get("/projects/123/").status_code, 404)


class DebugSettingTests(TestCase):
    @override_settings(DEBUG=True)
    def test_debug_flag_is_exposed_to_the_template(self) -> None:
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("<html", content)
        # The template embeds the flag for the client-side debug helper.
        self.assertIn("debug: true", content)
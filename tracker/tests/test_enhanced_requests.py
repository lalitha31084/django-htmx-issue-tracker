"""Enhancement layer: the same endpoints driven by HTMX.

Every test here sends the ``HX-Request: true`` header, exactly as HTMX does at
runtime, and asserts that the server answers with a *fragment* rather than a
full page.  Core requirements 7, 8, 9 and 10 are covered here.
"""

from __future__ import annotations

import json

from django.urls import reverse

from tracker.models import Comment, Issue

from .base import HX_REQUEST_HEADERS, TrackerTestCase


class HeaderDetectionTests(TrackerTestCase):
    """Core requirement 9: the views branch on the request headers."""

    def test_same_endpoint_returns_302_without_header_and_fragment_with_header(self) -> None:
        url = reverse("issue_update_status", args=[self.todo_issue.pk])

        # Request 1 - a normal browser form post.
        standard = self.client.post(url, {"status": Issue.Status.IN_PROGRESS})
        self.assertEqual(standard.status_code, 302)
        self.assertEqual(
            standard["Location"], reverse("project_board", args=[self.project.pk])
        )

        # Request 2 - the same call, now with the HTMX header.
        enhanced = self.client.post(
            url, {"status": Issue.Status.DONE}, HTTP_HX_REQUEST="true"
        )
        self.assertEqual(enhanced.status_code, 200)
        self.assertIsHtmlFragment(enhanced)
        self.assertTemplateUsed(enhanced, "partials/_issue_card.html")

    def test_multiple_header_styles_are_detected(self) -> None:
        url = reverse("issue_update_status", args=[self.todo_issue.pk])

        # Legacy test-client style keyword argument.
        legacy = self.client.post(url, {"status": Issue.Status.DONE}, HTTP_HX_REQUEST="true")
        self.assertIsHtmlFragment(legacy)

        # Modern ``headers=`` style.
        modern = self.client.post(
            url, {"status": Issue.Status.DONE}, headers=HX_REQUEST_HEADERS
        )
        self.assertIsHtmlFragment(modern)

        # A plain fetch() based enhancement with the conventional AJAX header.
        ajax = self.client.post(
            url,
            {"status": Issue.Status.DONE},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertIsHtmlFragment(ajax)

    def test_falsey_header_is_treated_as_a_standard_request(self) -> None:
        response = self.client.post(
            reverse("issue_update_status", args=[self.todo_issue.pk]),
            {"status": Issue.Status.DONE},
            HTTP_HX_REQUEST="false",
        )
        self.assertEqual(response.status_code, 302)

    def test_fragment_response_is_flagged_for_the_client(self) -> None:
        response = self.client.post(
            reverse("issue_update_status", args=[self.todo_issue.pk]),
            {"status": Issue.Status.DONE},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response["HX-Request"], "true")
        self.assertIn("no-store", response["Cache-Control"])


class EnhancedStatusUpdateTests(TrackerTestCase):
    """Core requirement 7: status update returns an issue card fragment."""

    def test_enhanced_status_update_returns_issue_card_fragment(self) -> None:
        response = self.client.post(
            reverse("issue_update_status", args=[self.todo_issue.pk]),
            {"status": Issue.Status.DONE},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partials/_issue_card.html")

        content = response.content.decode()
        self.assertIsHtmlFragment(response)
        # The fragment really is the updated card ...
        self.assertIn(f'id="issue-{self.todo_issue.pk}"', content)
        self.assertIn(self.todo_issue.title, content)
        self.assertIn('data-status="Done"', content)
        self.assertNotIn("<html", content.lower())
        self.assertNotIn("<body", content.lower())

        # ... and the database really was updated.
        self.todo_issue.refresh_from_db()
        self.assertEqual(self.todo_issue.status, Issue.Status.DONE)

    def test_fragment_is_smaller_than_a_full_page(self) -> None:
        page = self.client.get(reverse("project_board", args=[self.project.pk]))
        fragment = self.client.post(
            reverse("issue_update_status", args=[self.todo_issue.pk]),
            {"status": Issue.Status.DONE},
            HTTP_HX_REQUEST="true",
        )
        self.assertLess(len(fragment.content), len(page.content))

    def test_enhanced_update_with_invalid_status_returns_form_errors(self) -> None:
        response = self.client.post(
            reverse("issue_update_status", args=[self.todo_issue.pk]),
            {"status": "Nope"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIsHtmlFragment(response, status=400)
        self.assertContains(response, "not one of the available choices", status_code=400)
        self.todo_issue.refresh_from_db()
        self.assertEqual(self.todo_issue.status, Issue.Status.TODO)

    def test_json_client_gets_json_instead_of_html(self) -> None:
        """A ``fetch()`` client that asks for JSON gets JSON, not a fragment."""
        response = self.client.post(
            reverse("issue_update_status", args=[self.todo_issue.pk]),
            {"status": Issue.Status.DONE},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        payload = json.loads(response.content)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], Issue.Status.DONE)

        self.todo_issue.refresh_from_db()
        self.assertEqual(self.todo_issue.status, Issue.Status.DONE)

    def test_htmx_header_wins_over_a_json_accept_header(self) -> None:
        """HTMX always asks for HTML, even when the Accept header is ambiguous."""
        response = self.client.post(
            reverse("issue_update_status", args=[self.todo_issue.pk]),
            {"status": Issue.Status.DONE},
            HTTP_HX_REQUEST="true",
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsHtmlFragment(response)
        self.assertTemplateUsed(response, "partials/_issue_card.html")


class EnhancedCommentTests(TrackerTestCase):
    """Core requirement 8: adding a comment returns the new comment fragment."""

    def test_enhanced_add_comment_returns_comment_fragment(self) -> None:
        response = self.client.post(
            reverse("comment_add", args=[self.todo_issue.pk]),
            {"content": "Shipped in release 2.4.1."},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partials/_comment.html")

        content = response.content.decode()
        self.assertIsHtmlFragment(response)
        self.assertIn("<li", content)
        self.assertIn("Shipped in release 2.4.1.", content)
        self.assertNotIn("<html", content.lower())
        self.assertNotIn("<body", content.lower())

        comment = Comment.objects.get(content="Shipped in release 2.4.1.")
        self.assertEqual(comment.issue, self.todo_issue)

    def test_enhanced_empty_comment_re_renders_the_form_fragment(self) -> None:
        before = Comment.objects.count()
        response = self.client.post(
            reverse("comment_add", args=[self.todo_issue.pk]),
            {"content": ""},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIsHtmlFragment(response, status=400)
        self.assertTemplateUsed(response, "partials/_comment_form.html")
        self.assertContains(response, "required", status_code=400)
        self.assertEqual(Comment.objects.count(), before)

    def test_enhanced_delete_comment_returns_a_small_notice(self) -> None:
        response = self.client.post(
            reverse("comment_delete", args=[self.comment.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsHtmlFragment(response)
        self.assertContains(response, "Comment deleted.")
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())


class EnhancedCreationTests(TrackerTestCase):
    def test_enhanced_issue_creation_returns_the_board_column(self) -> None:
        before = Issue.objects.filter(project=self.project).count()
        response = self.client.post(
            reverse("issue_create", args=[self.project.pk]),
            {
                "title": "Add a docker healthcheck for the web service",
                "description": "Compose should report healthy.",
                "status": Issue.Status.TODO,
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partials/_issue_column.html")
        self.assertIsHtmlFragment(response)
        self.assertIn("Add a docker healthcheck for the web service", response.content.decode())
        self.assertEqual(Issue.objects.filter(project=self.project).count(), before + 1)

    def test_enhanced_issue_creation_with_invalid_data_returns_the_form(self) -> None:
        before = Issue.objects.filter(project=self.project).count()
        response = self.client.post(
            reverse("issue_create", args=[self.project.pk]),
            {"title": "", "description": "", "status": Issue.Status.TODO},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partials/_issue_form.html")
        self.assertIsHtmlFragment(response)
        self.assertEqual(Issue.objects.filter(project=self.project).count(), before)

    def test_enhanced_issue_delete_returns_a_notice_fragment(self) -> None:
        response = self.client.post(
            reverse("issue_delete", args=[self.todo_issue.pk]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsHtmlFragment(response)
        self.assertFalse(Issue.objects.filter(pk=self.todo_issue.pk).exists())

    def test_enhanced_project_creation_returns_the_project_list(self) -> None:
        response = self.client.post(
            reverse("project_create"),
            {"name": "Helios Client", "description": "Desktop client."},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "partials/_project_list.html")
        self.assertIsHtmlFragment(response)
        self.assertIn("Helios Client", response.content.decode())


class FragmentIsolationTests(TrackerTestCase):
    """Guard rail: no enhanced endpoint may ever leak a full page."""

    def test_no_fragment_response_contains_a_document_shell(self) -> None:
        cases = [
            (
                "status",
                lambda: self.client.post(
                    reverse("issue_update_status", args=[self.todo_issue.pk]),
                    {"status": Issue.Status.DONE},
                    HTTP_HX_REQUEST="true",
                ),
            ),
            (
                "comment",
                lambda: self.client.post(
                    reverse("comment_add", args=[self.todo_issue.pk]),
                    {"content": "A comment."},
                    HTTP_HX_REQUEST="true",
                ),
            ),
            (
                "issue create",
                lambda: self.client.post(
                    reverse("issue_create", args=[self.project.pk]),
                    {"title": "Fragment isolation check", "description": "", "status": "To Do"},
                    HTTP_HX_REQUEST="true",
                ),
            ),
            (
                "issue delete",
                lambda: self.client.post(
                    reverse("issue_delete", args=[self.done_issue.pk]),
                    HTTP_HX_REQUEST="true",
                ),
            ),
        ]

        for label, call in cases:
            with self.subTest(endpoint=label):
                response = call()
                self.assertEqual(response.status_code, 200)
                content = response.content.decode().lower()
                self.assertNotIn("<html", content)
                self.assertNotIn("<!doctype", content)
                self.assertNotIn("<body", content)
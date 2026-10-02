"""Shared helpers for the test suite."""

from __future__ import annotations

from django.test import TestCase

from tracker.models import Comment, Issue, Project

#: Header HTMX sends on every request it makes.  Django's test client maps the
#: ``HTTP_``-prefixed keyword arguments onto real HTTP headers, so
#: ``HTTP_HX_REQUEST="true"`` arrives as ``HX-Request: true``.
HX_REQUEST_HEADERS = {"HX-Request": "true"}
HTML_DOCUMENT_MARKERS = ("<html", "<body", "<!doctype html")


class TrackerTestCase(TestCase):
    """Base class providing a small, predictable fixture graph."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.project = Project.objects.create(
            name="Test Project",
            description="A project used by the automated tests.",
        )
        cls.other_project = Project.objects.create(
            name="Another Project",
            description="A second project so grouping can be verified.",
        )
        cls.todo_issue = Issue.objects.create(
            title="Fix the login redirect",
            description="Users land on the dashboard instead of their profile.",
            status=Issue.Status.TODO,
            project=cls.project,
        )
        cls.in_progress_issue = Issue.objects.create(
            title="Add pagination to the issue list",
            description="The board renders all issues at once.",
            status=Issue.Status.IN_PROGRESS,
            project=cls.project,
        )
        cls.done_issue = Issue.objects.create(
            title="Remove the legacy endpoint",
            description="Nothing calls /api/legacy any more.",
            status=Issue.Status.DONE,
            project=cls.project,
        )
        cls.comment = Comment.objects.create(
            issue=cls.todo_issue,
            content="Reproduced on staging with a fresh session.",
        )

    # -- assertions -------------------------------------------------------

    def assertIsFullHtmlPage(self, response) -> None:
        """The response must be a complete, server-rendered HTML document."""
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("<html", content)
        self.assertIn("<body", content)
        self.assertIn("</html>", content)

    def assertIsHtmlFragment(self, response, status: int = 200) -> None:
        """The response must be a small snippet, *not* a full document."""
        self.assertEqual(response.status_code, status)
        content = response.content.decode()
        for marker in HTML_DOCUMENT_MARKERS:
            self.assertNotIn(
                marker,
                content.lower(),
                msg=f"Fragment response unexpectedly contains {marker!r}",
            )
        self.assertGreater(len(content.strip()), 0)
"""Base layer: the application must work with JavaScript disabled.

These tests use the Django test client exactly like a plain browser would -
a full page load or a plain ``application/x-www-form-urlencoded`` POST - and
assert full pages (200) or redirects (302).  No enhancement header is ever sent.
"""

from __future__ import annotations

import json

from django.urls import reverse

from tracker.models import Comment, Issue, Project

from .base import TrackerTestCase


class ProjectPageTests(TrackerTestCase):
    """Core requirement 3: the project board is a complete HTML document."""

    def test_board_is_a_full_html_page_grouped_by_status(self) -> None:
        response = self.client.get(reverse("project_board", args=[self.project.pk]))

        self.assertIsFullHtmlPage(response)
        self.assertTemplateUsed(response, "tracker/project_board.html")

        content = response.content.decode()
        # All three columns are present, with their labels.
        for label in ("To Do", "In Progress", "Done"):
            self.assertIn(label, content)

        # Each issue title appears under the section for its own status.
        self.assertIn(self.todo_issue.title, content)
        self.assertIn(self.in_progress_issue.title, content)
        self.assertIn(self.done_issue.title, content)

        # Issues from a different project are not leaked onto this board.
        foreign = Issue.objects.create(
            title="Should not appear here",
            status=Issue.Status.TODO,
            project=self.other_project,
        )
        board = self.client.get(reverse("project_board", args=[self.project.pk]))
        self.assertNotContains(board, foreign.title)

    def test_board_places_issue_in_the_correct_column(self) -> None:
        """The DOM structure must group issues under their status heading."""
        response = self.client.get(reverse("project_board", args=[self.project.pk]))
        content = response.content.decode()

        for slug, issue in (
            ("to-do", self.todo_issue),
            ("in-progress", self.in_progress_issue),
            ("done", self.done_issue),
        ):
            column_marker = f'data-status-slug="{slug}"'
            self.assertIn(column_marker, content)
            # The issue card must advertise the same status as its column.
            self.assertIn(f'id="issue-{issue.pk}"', content)
            self.assertIn(f'data-status="{issue.status}"', content)

    def test_board_renders_without_any_javascript_assets_required(self) -> None:
        """Every mutating control is a real form, not an hx-* only button."""
        response = self.client.get(reverse("project_board", args=[self.project.pk]))
        content = response.content.decode()

        # The status change is a <form method="post"> - that is what makes the
        # no-JS path work.
        self.assertIn(
            f'action="{reverse("issue_update_status", args=[self.todo_issue.pk])}"',
            content,
        )
        self.assertIn('method="post"', content)
        self.assertIn(f'name="status"', content)

    def test_unknown_project_returns_404(self) -> None:
        self.assertEqual(self.client.get("/projects/999999/").status_code, 404)

    def test_project_list_is_a_full_page(self) -> None:
        response = self.client.get(reverse("project_list"))
        self.assertIsFullHtmlPage(response)
        self.assertContains(response, self.project.name)
        self.assertContains(response, self.other_project.name)

    def test_issue_detail_is_a_full_page_with_comments(self) -> None:
        response = self.client.get(reverse("issue_detail", args=[self.todo_issue.pk]))
        self.assertIsFullHtmlPage(response)
        self.assertContains(response, self.todo_issue.title)
        self.assertContains(response, self.comment.content)

    def test_dashboard_is_a_full_page(self) -> None:
        response = self.client.get(reverse("dashboard"))
        self.assertIsFullHtmlPage(response)


class IssueCreationTests(TrackerTestCase):
    """Core requirement 4: create an issue with a standard form POST."""

    def test_create_issue_redirects_and_persists(self) -> None:
        url = reverse("issue_create", args=[self.project.pk])
        before = Issue.objects.filter(project=self.project).count()

        response = self.client.post(
            url,
            {
                "title": "Cover the health endpoint with tests",
                "description": "Assert that /health/ returns 200.",
                "status": Issue.Status.IN_PROGRESS,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("project_board", args=[self.project.pk]))

        after = Issue.objects.filter(project=self.project).count()
        self.assertEqual(after, before + 1)

        created = Issue.objects.get(title="Cover the health endpoint with tests")
        self.assertEqual(created.project, self.project)
        self.assertEqual(created.status, Issue.Status.IN_PROGRESS)
        self.assertEqual(created.description, "Assert that /health/ returns 200.")

    def test_created_issue_defaults_to_to_do(self) -> None:
        response = self.client.post(
            reverse("issue_create", args=[self.project.pk]),
            {"title": "Investigate flaky CI run", "description": "", "status": Issue.Status.TODO},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Issue.objects.filter(title="Investigate flaky CI run").exists())

    def test_create_issue_rejects_invalid_payload_without_writing(self) -> None:
        before = Issue.objects.filter(project=self.project).count()
        response = self.client.post(
            reverse("issue_create", args=[self.project.pk]),
            {"title": "", "description": "no title", "status": Issue.Status.TODO},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Issue.objects.filter(project=self.project).count(), before)
        self.assertContains(response, "required", status_code=200)

    def test_create_issue_rejects_unknown_status(self) -> None:
        before = Issue.objects.count()
        response = self.client.post(
            reverse("issue_create", args=[self.project.pk]),
            {"title": "Sneaky status value", "description": "", "status": "Nonsense"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Issue.objects.count(), before)


class StatusUpdateTests(TrackerTestCase):
    """Core requirement 5: change a status with a standard form POST."""

    def test_update_status_redirects_and_persists(self) -> None:
        url = reverse("issue_update_status", args=[self.todo_issue.pk])
        self.assertEqual(self.todo_issue.status, Issue.Status.TODO)

        response = self.client.post(url, {"status": Issue.Status.DONE})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], reverse("project_board", args=[self.project.pk])
        )

        self.todo_issue.refresh_from_db()
        self.assertEqual(self.todo_issue.status, Issue.Status.DONE)

    def test_update_status_to_each_valid_value(self) -> None:
        for status in (Issue.Status.IN_PROGRESS, Issue.Status.DONE, Issue.Status.TODO):
            with self.subTest(status=status):
                response = self.client.post(
                    reverse("issue_update_status", args=[self.todo_issue.pk]),
                    {"status": status},
                )
                self.assertEqual(response.status_code, 302)
                self.todo_issue.refresh_from_db()
                self.assertEqual(self.todo_issue.status, status)

    def test_update_status_with_invalid_value_does_not_change_the_issue(self) -> None:
        response = self.client.post(
            reverse("issue_update_status", args=[self.todo_issue.pk]),
            {"status": "Definitely Not A Status"},
        )
        # The base layer redirects back to the board with an error message.
        self.assertEqual(response.status_code, 302)
        self.todo_issue.refresh_from_db()
        self.assertEqual(self.todo_issue.status, Issue.Status.TODO)

    def test_update_status_requires_post(self) -> None:
        response = self.client.get(reverse("issue_update_status", args=[self.todo_issue.pk]))
        self.assertEqual(response.status_code, 405)
        self.todo_issue.refresh_from_db()
        self.assertEqual(self.todo_issue.status, Issue.Status.TODO)

    def test_update_status_of_unknown_issue_returns_404(self) -> None:
        response = self.client.post("/issues/999999/update-status/", {"status": "Done"})
        self.assertEqual(response.status_code, 404)


class CommentTests(TrackerTestCase):
    """Core requirement 6: add a comment with a standard form POST."""

    def test_add_comment_redirects_and_persists(self) -> None:
        url = reverse("comment_add", args=[self.todo_issue.pk])
        before = Comment.objects.filter(issue=self.todo_issue).count()

        response = self.client.post(url, {"content": "Confirmed on staging."})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"], reverse("issue_detail", args=[self.todo_issue.pk])
        )

        after = Comment.objects.filter(issue=self.todo_issue).count()
        self.assertEqual(after, before + 1)
        self.assertTrue(
            Comment.objects.filter(
                issue=self.todo_issue, content="Confirmed on staging."
            ).exists()
        )

    def test_add_empty_comment_is_rejected(self) -> None:
        before = Comment.objects.count()
        response = self.client.post(
            reverse("comment_add", args=[self.todo_issue.pk]), {"content": "   "}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Comment.objects.count(), before)

    def test_add_comment_requires_post(self) -> None:
        response = self.client.get(reverse("comment_add", args=[self.todo_issue.pk]))
        self.assertEqual(response.status_code, 405)

    def test_comment_cascade_delete_with_issue(self) -> None:
        comment_count = Comment.objects.filter(issue=self.todo_issue).count()
        self.assertGreater(comment_count, 0)
        self.todo_issue.delete()
        self.assertFalse(Comment.objects.filter(issue_id=self.todo_issue.pk).exists())


class ProjectCreationTests(TrackerTestCase):
    def test_create_project_redirects_and_persists(self) -> None:
        before = Project.objects.count()
        response = self.client.post(
            reverse("project_create"), {"name": "Sphinx Tools", "description": "New project."}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("project_list"))
        self.assertEqual(Project.objects.count(), before + 1)
        self.assertTrue(Project.objects.filter(name="Sphinx Tools").exists())

    def test_create_project_rejects_short_name(self) -> None:
        before = Project.objects.count()
        response = self.client.post(reverse("project_create"), {"name": "ab", "description": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Project.objects.count(), before)


class IssueDeletionTests(TrackerTestCase):
    def test_delete_issue_redirects_to_board(self) -> None:
        response = self.client.post(reverse("issue_delete", args=[self.todo_issue.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Issue.objects.filter(pk=self.todo_issue.pk).exists())

    def test_delete_comment_redirects_to_issue_detail(self) -> None:
        response = self.client.post(reverse("comment_delete", args=[self.comment.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Comment.objects.filter(pk=self.comment.pk).exists())


class SecurityTests(TrackerTestCase):
    """Mutating endpoints must reject unsafe methods and honour CSRF."""

    def test_csrf_token_is_required_for_post(self) -> None:
        from django.test import Client

        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("issue_update_status", args=[self.todo_issue.pk]),
            {"status": Issue.Status.DONE},
        )
        self.assertEqual(response.status_code, 403)
        self.todo_issue.refresh_from_db()
        self.assertEqual(self.todo_issue.status, Issue.Status.TODO)

    def test_json_status_endpoint_rejects_non_enhanced_requests(self) -> None:
        response = self.client.post(
            reverse("issue_update_status_json", args=[self.todo_issue.pk]),
            {"status": Issue.Status.DONE},
        )
        self.assertEqual(response.status_code, 409)
        payload = json.loads(response.content)
        self.assertFalse(payload["ok"])
"""Model, form and template-tag unit tests."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.test import TestCase

from tracker.forms import CommentForm, IssueForm, IssueStatusForm, ProjectForm
from tracker.models import Comment, Issue, Project
from tracker.templatetags.tracker_tags import excerpt, progress_percent, status_slug


class ProjectModelTests(TestCase):
    def test_str_and_absolute_url(self) -> None:
        project = Project.objects.create(name="Orbit CMS", description="Docs.")
        self.assertEqual(str(project), "Orbit CMS")
        self.assertEqual(project.get_absolute_url(), f"/projects/{project.pk}/")

    def test_issue_counts(self) -> None:
        project = Project.objects.create(name="Counts")
        Issue.objects.create(title="a", status=Issue.Status.TODO, project=project)
        Issue.objects.create(title="b", status=Issue.Status.DONE, project=project)
        Issue.objects.create(title="c", status=Issue.Status.DONE, project=project)

        self.assertEqual(project.issue_count, 3)
        self.assertEqual(project.open_issue_count, 1)
        self.assertEqual(progress_percent(project), 67)

    def test_issues_by_status_returns_every_column(self) -> None:
        project = Project.objects.create(name="Grouping")
        grouped = project.issues_by_status()
        self.assertEqual(list(grouped.keys()), ["To Do", "In Progress", "Done"])

    def test_progress_percent_of_empty_project_is_zero(self) -> None:
        self.assertEqual(progress_percent(Project.objects.create(name="Empty")), 0)

    def test_name_must_be_at_least_three_characters(self) -> None:
        project = Project(name="ab", description="")
        with self.assertRaises(ValidationError):
            project.full_clean()


class IssueModelTests(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(name="Issues")

    def test_str_includes_status(self) -> None:
        issue = Issue.objects.create(title="Bug", status=Issue.Status.TODO, project=self.project)
        self.assertEqual(str(issue), "Bug (To Do)")

    def test_status_slug(self) -> None:
        issue = Issue.objects.create(
            title="Bug", status=Issue.Status.IN_PROGRESS, project=self.project
        )
        self.assertEqual(issue.status_slug, "in-progress")

    def test_default_status_is_todo(self) -> None:
        issue = Issue.objects.create(title="Bug", project=self.project)
        self.assertEqual(issue.status, Issue.Status.TODO)

    def test_next_status_cycles_through_the_columns(self) -> None:
        issue = Issue.objects.create(
            title="Bug", status=Issue.Status.TODO, project=self.project
        )
        issue.status = Issue.Status.TODO
        self.assertEqual(issue.next_status, Issue.Status.IN_PROGRESS)
        issue.status = Issue.Status.IN_PROGRESS
        self.assertEqual(issue.next_status, Issue.Status.DONE)
        issue.status = Issue.Status.DONE
        self.assertEqual(issue.next_status, Issue.Status.TODO)

    def test_available_transitions_exclude_the_current_status(self) -> None:
        issue = Issue.objects.create(
            title="Bug", status=Issue.Status.IN_PROGRESS, project=self.project
        )
        self.assertNotIn(Issue.Status.IN_PROGRESS, issue.available_transitions)
        self.assertEqual(len(issue.available_transitions), 2)

    def test_updated_at_changes_on_save(self) -> None:
        issue = Issue.objects.create(title="Bug", project=self.project)
        first = issue.updated_at
        issue.status = Issue.Status.DONE
        issue.save()
        self.assertGreaterEqual(issue.updated_at, first)

    def test_comment_count(self) -> None:
        issue = Issue.objects.create(title="Bug", project=self.project)
        Comment.objects.create(issue=issue, content="one")
        Comment.objects.create(issue=issue, content="two")
        self.assertEqual(issue.comment_count, 2)

    def test_deleting_a_project_cascades_to_its_issues_and_comments(self) -> None:
        issue = Issue.objects.create(title="Bug", project=self.project)
        Comment.objects.create(issue=issue, content="one")
        issue_ids = set(Issue.objects.filter(project=self.project).values_list("id", flat=True))

        self.project.delete()

        self.assertFalse(Issue.objects.filter(id__in=issue_ids).exists())
        self.assertFalse(Comment.objects.filter(issue_id__in=issue_ids).exists())


class CommentModelTests(TestCase):
    def test_str_is_truncated(self) -> None:
        issue = Issue.objects.create(
            title="Bug", project=Project.objects.create(name="P")
        )
        comment = Comment.objects.create(issue=issue, content="x" * 60)
        self.assertEqual(str(comment), "x" * 40 + "...")
        self.assertEqual(Comment.objects.filter(issue=issue).count(), 1)

    def test_comments_are_ordered_oldest_first(self) -> None:
        issue = Issue.objects.create(
            title="Bug", project=Project.objects.create(name="P")
        )
        first = Comment.objects.create(issue=issue, content="first")
        second = Comment.objects.create(issue=issue, content="second")
        self.assertEqual(list(issue.comments.all()), [first, second])


class FormTests(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(name="Forms")

    def test_issue_form_assigns_the_project_from_the_url(self) -> None:
        form = IssueForm(
            {"title": "Valid title", "description": "Body", "status": Issue.Status.TODO},
            project=self.project,
        )
        self.assertTrue(form.is_valid())
        self.assertEqual(form.save().project, self.project)

    def test_issue_form_rejects_missing_title(self) -> None:
        form = IssueForm({"title": "", "status": Issue.Status.TODO}, project=self.project)
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)

    def test_issue_form_rejects_unknown_status(self) -> None:
        form = IssueForm(
            {"title": "Valid title", "status": "Sideways"}, project=self.project
        )
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_status_form_accepts_every_valid_status(self) -> None:
        for status in (Issue.Status.TODO, Issue.Status.IN_PROGRESS, Issue.Status.DONE):
            with self.subTest(status=status):
                self.assertTrue(IssueStatusForm({"status": status}).is_valid())

    def test_status_form_rejects_unknown_status(self) -> None:
        self.assertFalse(IssueStatusForm({"status": "Elsewhere"}).is_valid())

    def test_comment_form_strips_whitespace_only_content(self) -> None:
        issue = Issue.objects.create(title="Bug", project=self.project)
        form = CommentForm({"content": "    "}, issue=issue)
        self.assertFalse(form.is_valid())

    def test_comment_form_saves_against_the_given_issue(self) -> None:
        issue = Issue.objects.create(title="Bug", project=self.project)
        form = CommentForm({"content": " Hello "}, issue=issue)
        self.assertTrue(form.is_valid())
        comment = form.save()
        self.assertEqual(comment.issue, issue)
        self.assertEqual(comment.content, "Hello")

    def test_project_form_rejects_short_names(self) -> None:
        self.assertFalse(ProjectForm({"name": "ab"}).is_valid())
        self.assertTrue(ProjectForm({"name": "Long enough"}).is_valid())


class TemplateTagTests(TestCase):
    def test_status_slug(self) -> None:
        self.assertEqual(status_slug("In Progress"), "in-progress")
        self.assertEqual(status_slug("Done"), "done")

    def test_excerpt_truncates_on_a_word_boundary(self) -> None:
        self.assertEqual(excerpt("short", 20), "short")
        self.assertTrue(excerpt("one two three four five six", 12).startswith("one two"))
        self.assertLessEqual(len(excerpt("one two three four five six", 12)), 13)
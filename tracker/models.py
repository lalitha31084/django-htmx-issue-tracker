"""Database models for the issue tracker.

Schema (as required by the specification)::

    tracker_project   id, name, description, created_at
    tracker_issue     id, title, description, status, project_id,
                      created_at, updated_at
    tracker_comment   id, content, issue_id, created_at

The ``status`` column stores the human readable column label
(``"To Do"`` / ``"In Progress"`` / ``"Done"``).  Storing the label instead of a
machine code keeps the raw SQL readable for anyone auditing the database and
means the literal values in the specification match the stored values.
"""

from django.core.validators import MinLengthValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Project(models.Model):
    """A software project that owns a set of issues."""

    name = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(3)],
        help_text="Short, human readable name of the project.",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional longer description of what the project does.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        verbose_name_plural = "projects"

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("project_board", args=[self.pk])

    @property
    def open_issue_count(self) -> int:
        """Number of issues that are not yet done."""
        return self.issues.exclude(status=Issue.Status.DONE).count()

    def issues_by_status(self) -> dict[str, "models.QuerySet[Issue]"]:
        """Return ``{status_label: queryset}`` for every board column.

        The key order matches ``Issue.Status.choices`` so the board columns are
        always rendered in a predictable order.
        """
        grouped: dict[str, models.QuerySet] = {}
        for value, label in Issue.Status.choices:
            grouped[label] = self.issues.filter(status=value).order_by("id")
        return grouped

    @property
    def issue_count(self) -> int:
        return self.issues.count()


class Issue(models.Model):
    """A bug, task or story belonging to a :class:`Project`."""

    class Status(models.TextChoices):
        """The three board columns.

        ``label`` doubles as the database value (see module docstring).
        """

        TODO = "To Do", "To Do"
        IN_PROGRESS = "In Progress", "In Progress"
        DONE = "Done", "Done"

    title = models.CharField(
        max_length=200,
        validators=[MinLengthValidator(3)],
        help_text="Concise summary of the issue.",
    )
    description = models.TextField(
        blank=True,
        help_text="Longer description, steps to reproduce, expected behaviour, ...",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
        db_index=True,
        help_text="Which board column the issue currently sits in.",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="issues",
        help_text="Project this issue belongs to.",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "id"]
        indexes = [
            models.Index(fields=["project", "status"], name="issue_project_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"

    def get_absolute_url(self) -> str:
        return reverse("issue_detail", args=[self.pk])

    @property
    def status_slug(self) -> str:
        """URL/HTML friendly version of :attr:`status` (``"In Progress"`` -> ``"in-progress"``)."""
        return self.status.lower().replace(" ", "-")

    @property
    def available_transitions(self) -> list[str]:
        """Every status this issue can be moved to (including its current one)."""
        return [value for value, _label in self.Status.choices if value != self.status]

    @property
    def next_status(self) -> str | None:
        """The status one column to the right, wrapping back to the first column."""
        values = [value for value, _label in self.Status.choices]
        try:
            index = values.index(self.status)
        except ValueError:  # pragma: no cover - defensive, status is validated
            return values[0]
        return values[(index + 1) % len(values)]

    @property
    def comment_count(self) -> int:
        return self.comments.count()


class Comment(models.Model):
    """A comment left on an :class:`Issue`."""

    content = models.TextField(validators=[MinLengthValidator(1)])
    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        preview = self.content[:40]
        suffix = "..." if len(self.content) > 40 else ""
        return f"{preview}{suffix}"
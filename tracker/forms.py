"""Forms used by both the no-JavaScript and the enhanced request flows.

The *same* form classes are bound to the plain ``<form>`` markup and to the
HTMX ``hx-post`` attributes, so validation behaviour is identical whether or not
JavaScript is available.
"""

from __future__ import annotations

from django import forms

from .models import Comment, Issue, Project

__all__ = ["CommentForm", "IssueForm", "ProjectForm", "IssueStatusForm"]


class IssueForm(forms.ModelForm):
    """Create/update form for an :class:`~tracker.models.Issue`."""

    class Meta:
        model = Issue
        fields = ["title", "description", "status"]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "field-input",
                    "placeholder": "Short summary of the issue",
                    "autocomplete": "off",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "field-input",
                    "rows": 4,
                    "placeholder": "Details, steps to reproduce, expected behaviour ...",
                }
            ),
            "status": forms.Select(attrs={"class": "field-input"}),
        }

    def __init__(self, *args, project: Project | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.project = project
        if project is not None:
            # Issues always belong to the project taken from the URL, never from
            # a hidden form field that a client could tamper with.
            self.instance.project = project
        self.fields["status"].required = True
        self.fields["description"].required = False


class IssueStatusForm(forms.Form):
    """Tiny form used by the board's "move to ..." buttons.

    Keeping this a ``Form`` (rather than reading ``request.POST`` directly)
    means an invalid status produces a validation error instead of a 500.
    """

    status = forms.ChoiceField(
        choices=Issue.Status.choices,
        label="Status",
        widget=forms.HiddenInput,
    )

    def clean_status(self) -> str:
        status = self.cleaned_data["status"]
        valid = {value for value, _label in Issue.Status.choices}
        if status not in valid:
            raise forms.ValidationError(
                f"'{status}' is not a valid status. Choose one of: "
                + ", ".join(sorted(valid))
                + "."
            )
        return status


class CommentForm(forms.ModelForm):
    """Form used to add a comment to an issue."""

    class Meta:
        model = Comment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "class": "field-input",
                    "rows": 3,
                    "placeholder": "Leave a comment ...",
                }
            )
        }

    def __init__(self, *args, issue: Issue | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.issue = issue
        if issue is not None:
            self.instance.issue = issue
        self.fields["content"].required = True
        self.fields["content"].label = "Comment"

    def clean_content(self) -> str:
        content = (self.cleaned_data.get("content") or "").strip()
        if not content:
            raise forms.ValidationError("A comment cannot be empty.")
        return content


class ProjectForm(forms.ModelForm):
    """Create/edit form for a :class:`~tracker.models.Project`."""

    class Meta:
        model = Project
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "field-input", "placeholder": "Project name"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "field-input",
                    "rows": 3,
                    "placeholder": "What is this project about?",
                }
            ),
        }

    def clean_name(self) -> str:
        name = (self.cleaned_data.get("name") or "").strip()
        if len(name) < 3:
            raise forms.ValidationError("The project name must be at least 3 characters long.")
        return name
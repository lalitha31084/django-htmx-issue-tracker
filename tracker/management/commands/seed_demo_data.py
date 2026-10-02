"""``manage.py seed_demo_data`` - idempotent demo data loader.

The same data is also inserted by migration ``0002_seed_demo_data``, so a fresh
``docker compose up`` is already populated.  This command exists for the cases
where seeding needs to happen later (or on demand)::

    python manage.py seed_demo_data            # add missing demo data
    python manage.py seed_demo_data --flush    # wipe demo data and re-create it
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from tracker.models import Comment, Issue, Project
from tracker.seed_data import SEED_PROJECTS


class Command(BaseCommand):
    help = "Seed the database with demo projects, issues and comments."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete the demo data first, then recreate it.",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        flush = options["flush"]

        if flush:
            names = [project["name"] for project in SEED_PROJECTS]
            deleted, _ = Project.objects.filter(name__in=names).delete()
            self.stdout.write(self.style.WARNING(f"Removed {deleted} demo objects."))

        projects = issues = comments = 0
        for project_data in SEED_PROJECTS:
            project, created = Project.objects.get_or_create(
                name=project_data["name"],
                defaults={"description": project_data["description"]},
            )
            projects += int(created)

            for issue_data in project_data["issues"]:
                issue, issue_created = Issue.objects.get_or_create(
                    project=project,
                    title=issue_data["title"],
                    defaults={
                        "description": issue_data["description"],
                        "status": issue_data["status"],
                    },
                )
                issues += int(issue_created)

                for text in issue_data.get("comments", []):
                    _comment, comment_created = Comment.objects.get_or_create(
                        issue=issue, content=text
                    )
                    comments += int(comment_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded demo data: {projects} new project(s), {issues} new issue(s), "
                f"{comments} new comment(s). "
                f"Database now holds {Project.objects.count()} project(s), "
                f"{Issue.objects.count()} issue(s) and {Comment.objects.count()} comment(s)."
            )
        )
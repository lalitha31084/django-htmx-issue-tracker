"""Seed the database with demo projects, issues and comments.

Why a *data migration* rather than a management command?

The requirement is "the database must be automatically seeded on startup".  A
data migration guarantees that:

* it runs inside the same ``migrate`` step the entrypoint already performs, so
  there is nothing extra to remember;
* it is transactional and tracked, so ``migrate` is idempotent;
* it produces the same data in local development, in the test suite and in a
  fresh Docker volume.

The migration is written defensively: it looks objects up before creating them,
so applying it to a database that already holds data is a no-op.  The
``seed_demo_data`` management command reuses the exact same function and can
therefore be run repeatedly.
"""

from django.db import migrations

from tracker.seed_data import SEED_PROJECTS


def seed(apps, schema_editor):
    """Insert the demo data using the historical model registry."""
    Project = apps.get_model("tracker", "Project")
    Issue = apps.get_model("tracker", "Issue")
    Comment = apps.get_model("tracker", "Comment")

    # Do not double-seed when a database is migrated more than once.
    if Project.objects.exists():
        return

    for project_data in SEED_PROJECTS:
        project, _created = Project.objects.get_or_create(
            name=project_data["name"],
            defaults={"description": project_data["description"]},
        )

        for issue_data in project_data["issues"]:
            issue, _created = Issue.objects.get_or_create(
                project=project,
                title=issue_data["title"],
                defaults={
                    "description": issue_data["description"],
                    "status": issue_data["status"],
                },
            )
            for comment_text in issue_data.get("comments", []):
                Comment.objects.get_or_create(issue=issue, content=comment_text)


def unseed(apps, schema_editor):
    """Remove the demo data again (used by ``migrate tracker 0001``)."""
    Project = apps.get_model("tracker", "Project")
    Issue = apps.get_model("tracker", "Issue")
    Comment = apps.get_model("tracker", "Comment")

    names = [project["name"] for project in SEED_PROJECTS]
    projects = Project.objects.filter(name__in=names)
    issue_ids = Issue.objects.filter(project__in=projects).values_list("id", flat=True)
    Comment.objects.filter(issue_id__in=list(issue_ids)).delete()
    Issue.objects.filter(id__in=list(issue_ids)).delete()
    projects.delete()


class Migration(migrations.Migration):
    dependencies = [("tracker", "0001_initial")]

    operations = [migrations.RunPython(seed, unseed)]
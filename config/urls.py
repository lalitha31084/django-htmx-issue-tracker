"""Root URL configuration.

The public, no-JavaScript-first routes all live at the project level:

======================================================  ==========================
URL                                                     View
======================================================  ==========================
``/``                                                    dashboard / project list
``/projects/``                                           project list
``/projects/<id>/``                                      issue board
``/projects/<id>/issues/create/``                        create an issue
``/issues/<id>/``                                        issue detail
``/issues/<id>/update-status/``                          change an issue status
``/issues/<id>/comments/add/``                           add a comment
``/issues/<id>/delete/``                                 delete an issue
``/health/``                                             container health probe
======================================================  ==========================
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from tracker import views as tracker_views

urlpatterns = [
    path("", tracker_views.dashboard, name="dashboard"),
    path("projects/", tracker_views.project_list, name="project_list"),
    path("projects/create/", tracker_views.project_create, name="project_create"),
    path(
        "projects/<int:project_id>/",
        tracker_views.project_board,
        name="project_board",
    ),
    path(
        "projects/<int:project_id>/issues/create/",
        tracker_views.issue_create,
        name="issue_create",
    ),
    path(
        "projects/<int:project_id>/edit/",
        tracker_views.project_edit,
        name="project_edit",
    ),
    path("issues/<int:issue_id>/", tracker_views.issue_detail, name="issue_detail"),
    path("issues/<int:issue_id>/edit/", tracker_views.issue_edit, name="issue_edit"),
    path(
        "issues/<int:issue_id>/update-status/",
        tracker_views.update_issue_status,
        name="issue_update_status",
    ),
    path(
        "issues/<int:issue_id>/update-status/json/",
        tracker_views.update_issue_status_json,
        name="issue_update_status_json",
    ),
    path(
        "issues/<int:issue_id>/comments/add/",
        tracker_views.add_comment,
        name="comment_add",
    ),
    path(
        "issues/<int:issue_id>/delete/",
        tracker_views.issue_delete,
        name="issue_delete",
    ),
    path(
        "comments/<int:comment_id>/delete/",
        tracker_views.delete_comment,
        name="comment_delete",
    ),
    # Liveness / readiness probe used by the Docker healthcheck.
    path("health/", tracker_views.health, name="health"),
    path("health/db/", tracker_views.health_db, name="health_db"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
]
"""Admin registrations - handy for manual inspection during development."""

from django.contrib import admin

from .models import Comment, Issue, Project


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ["content", "created_at"]
    readonly_fields = ["created_at"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "issue_count", "created_at"]
    search_fields = ["name", "description"]
    ordering = ["name"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("issues")


@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "project", "status", "updated_at"]
    list_filter = ["status", "project"]
    search_fields = ["title", "description"]
    list_editable = ["status"]
    inlines = [CommentInline]
    autocomplete_fields = []
    date_hierarchy = "created_at"


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "issue", "created_at"]
    search_fields = ["content"]
    list_filter = ["created_at"]
from django.contrib import admin

from .models import ReviewAction


class NamedUserCreatedObjectAdmin(admin.ModelAdmin):
    """Shared admin configuration for NamedUserCreatedObject subclasses."""

    list_display = ("name", "owner", "publication_status")
    search_fields = ("name",)
    list_filter = ("publication_status",)
    ordering = ("name",)


@admin.register(ReviewAction)
class ReviewActionAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "action",
        "user",
        "content_type",
        "object_id",
        "created_at",
    )
    search_fields = ("comment", "user__username")
    list_filter = ("action", "content_type", "created_at")
    ordering = ("-created_at",)

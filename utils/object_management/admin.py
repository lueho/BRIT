from django.contrib import admin

from .models import ReviewAction


@admin.register(ReviewAction)
class ReviewActionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "action", "user", "content_type", "object_id", "created_at")
    search_fields = ("comment", "user__username")
    list_filter = ("action", "content_type", "created_at")
    ordering = ("-created_at",)

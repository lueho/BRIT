from django.contrib import admin


class BaseUserCreatedObjectModelAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', 'created_by', 'lastmodified_at', 'lastmodified_by')

import logging
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone

from .storages import get_file_export_storage

DEFAULT_RETENTION_DAYS = 7

logger = logging.getLogger(__name__)


def default_expires_at():
    retention_days = getattr(
        settings, "FILE_EXPORT_RETENTION_DAYS", DEFAULT_RETENTION_DAYS
    )
    return timezone.now() + timedelta(days=retention_days)


class UserExportQuerySet(models.QuerySet):
    def active(self):
        return self.filter(expires_at__gt=timezone.now())

    def expired(self):
        return self.filter(expires_at__lte=timezone.now())


class UserExport(models.Model):
    """Record of a file export performed by a user.

    Keeps the metadata needed to re-download the exported file from temporary
    storage until it expires.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="file_exports",
    )
    model_label = models.CharField(max_length=255)
    file_format = models.CharField(max_length=10)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField(null=True, blank=True)
    row_count = models.IntegerField(null=True, blank=True)
    filter_params = models.JSONField(default=dict, blank=True)
    task_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expires_at, db_index=True)

    objects = UserExportQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.model_label} export ({self.file_format}) by {self.owner}"

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    def get_download_url(self):
        return get_file_export_storage().url(self.file_name)

    def delete_file(self):
        storage = get_file_export_storage()
        if storage.exists(self.file_name):
            storage.delete(self.file_name)


@receiver(pre_delete, sender=UserExport)
def delete_export_file_on_record_delete(sender, instance, **kwargs):
    """Remove the stored file when its record is deleted, including cascades."""
    try:
        instance.delete_file()
    except Exception:
        logger.exception("Could not delete export file %s", instance.file_name)

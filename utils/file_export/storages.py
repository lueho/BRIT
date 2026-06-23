from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage


class TempUserFileDownloadStorage(S3Boto3Storage):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = "tmp"


def get_file_export_storage():
    if getattr(settings, "FILE_EXPORT_USE_LOCAL_STORAGE", False):
        location = Path(settings.MEDIA_ROOT) / "tmp"
        location.mkdir(parents=True, exist_ok=True)
        return FileSystemStorage(
            location=location,
            base_url=f"{settings.MEDIA_URL.rstrip('/')}/tmp/",
        )
    return TempUserFileDownloadStorage()


def write_file_for_download(file_name, data, renderer_class):
    storage = get_file_export_storage()
    renderer = renderer_class()
    with storage.open(file_name, "wb") as file:
        renderer.render(file, data)
    return storage.url(file_name)

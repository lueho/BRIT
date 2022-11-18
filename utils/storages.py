from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings


class TempUserFileDownloadStorage(S3Boto3Storage):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    location = 'tmp'


def write_file_for_download(file_name, data, renderer_class):
    storage = TempUserFileDownloadStorage()
    renderer = renderer_class()
    with storage.open(file_name, 'w') as file:
        renderer.render(file, data)
    return storage.url(file_name)

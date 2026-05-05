from storages.backends.s3boto3 import S3ManifestStaticStorage


class StaticStorage(S3ManifestStaticStorage):
    location = "static"
    file_overwrite = True

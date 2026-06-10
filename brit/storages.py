from storages.backends.s3boto3 import S3ManifestStaticStorage


class StaticStorage(S3ManifestStaticStorage):
    location = "static"
    # The manifest must be replaced on every collectstatic run so templates
    # resolve to the latest content-hashed asset filenames.
    file_overwrite = True

from django.core.management.base import BaseCommand, CommandError
import os
import subprocess


class Command(BaseCommand):
    help = 'Captures current state of production database and integrates it to dev db.'

    @staticmethod
    def capture():
        os.system(f'heroku pg:backups:capture {os.environ.get("HEROKU_POSTGRESQL_COLOR_URL")}')

    @staticmethod
    def download(file_name):
        os.system(f'heroku pg:backups:download -a {os.environ.get("HEROKU_APP_NAME")} -o {file_name}')

    @staticmethod
    def restore_local_db(file_name):
        database = os.environ.get('POSTGRES_DB')
        host = os.environ.get('POSTGRES_HOST')
        port = os.environ.get('POSTGRES_PORT')
        user = os.environ.get('POSTGRES_USER')
        os.system(f'pg_restore --clean --no-acl --no-owner -h {host} -p {port} -U {user} -d {database} {file_name}')

    @staticmethod
    def restore_production_db(url):
        app_name = os.environ.get('HEROKU_APP_NAME')
        db_url = os.environ.get('HEROKU_POSTGRESQL_COLOR_URL')
        os.system(f'heroku pg:backups:restore -a {app_name} --confirm {app_name} \'{url}\' {db_url}')

    @staticmethod
    def presign_aws_bucket_url(bucket_name, file_name):
        stream = os.popen(f'aws s3 presign s3://{bucket_name}/{file_name}')
        return stream.read().strip()

    def handle(self, *args, **options):
        os.chdir('./db_dump')
        s3_bucket_name = os.environ.get('S3_BUCKET_NAME')
        file_name = 'latest.dump'
        path = os.path.join(os.getcwd(), file_name)
        if os.path.exists(path):
            os.remove(path)

        # self.capture()
        # self.download(file_name)
        url = self.presign_aws_bucket_url(s3_bucket_name, file_name)
        self.restore_production_db(url)

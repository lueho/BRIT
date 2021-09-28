from django.core.management.base import BaseCommand
import os


class Command(BaseCommand):
    help = 'Captures current state of production database and integrates it to dev db.'

    def add_arguments(self, parser):
        parser.add_argument('action', type=str, help='Defines the action to be taken on the database')

    @staticmethod
    def capture():
        """
        Creates a backup of the current production database within the Heroku system.
        """
        os.system(f'heroku pg:backups:capture {os.environ.get("HEROKU_POSTGRESQL_COLOR_URL")}')

    @staticmethod
    def download(file_name):
        """
        Downlaods a stored production database backup from heroku as local dump file.
        """
        os.system(f'heroku pg:backups:download -a {os.environ.get("HEROKU_APP_NAME")} -o {file_name}')

    @staticmethod
    def dump_local_db(file_name):
        """
        Creates a dump file from the local development database.
        """
        user = os.environ.get('POSTGRES_USER')
        password = os.environ.get('POSTGRES_PASSWORD')
        os.system(f'export PGPASSWORD={password}')
        os.system(f'pg_dump -Fc --no-acl --no-owner -h db -p 5432 -U {user} > {file_name}')

    @staticmethod
    def restore_local_db(file_name):
        """
        Writes a local dump file into the local development database.
        """
        database = os.environ.get('POSTGRES_DB')
        host = os.environ.get('POSTGRES_HOST')
        port = os.environ.get('POSTGRES_PORT')
        user = os.environ.get('POSTGRES_USER')
        os.system(f'pg_restore --clean --no-acl --no-owner -h {host} -p {port} -U {user} -d {database} {file_name}')

    def restore_production_db(self, file_name):
        """
        Downloads the dump file from the configured s3 bucket and writes it into the production database.
        """
        app_name = os.environ.get('HEROKU_APP_NAME')
        db_url = os.environ.get('HEROKU_POSTGRESQL_COLOR_URL')

        path = os.path.join(os.getcwd(), file_name)
        if os.path.exists(path):
            os.remove(path)

        url = self.presign_aws_bucket_url(file_name)
        os.system(f'heroku pg:backups:restore -a {app_name} --confirm {app_name} \'{url}\' {db_url}')

    @staticmethod
    def store(file_name):
        """
        Uploads a local database dump file into the configured s3 bucket.
        """
        s3_bucket_name = os.environ.get('S3_BUCKET_NAME')
        os.system(f'aws s3 cp {file_name} s3://{s3_bucket_name}/{file_name}')

    @staticmethod
    def presign_aws_bucket_url(file_name):
        """
        Creates a presigned url of the database dumpfile stored in the s3 bucket. This url can than be used by
        Heroku to implement this dump file as new database content.
        """
        bucket_name = os.environ.get('S3_BUCKET_NAME')
        stream = os.popen(f'aws s3 presign s3://{bucket_name}/{file_name}')
        return stream.read().strip()

    def pull(self):
        """
        Creates a backup of the current production database and writes it into the local development database.
        """
        file_name = 'latest.dump'
        self.capture()
        self.download(file_name)
        self.restore_local_db(file_name)

    def push(self):
        """
        Pushes the current local development database into the production database. WARNING: All data on production
        will be overwritten. To avoid data loss, pull production data first.
        """
        file_name = 'latest.dump'
        self.dump_local_db(file_name)
        self.store(file_name)
        self.restore_production_db(file_name)

    def handle(self, *args, **options):
        os.chdir('./db_dump')
        file_name = 'latest.dump'

        action = options['action']
        if action == 'capture':
            self.capture()
        elif action == 'download':
            self.download(file_name)
        elif action == 'dump':
            self.dump_local_db(file_name)
        elif action == 'restore_local':
            self.restore_local_db(file_name)
        elif action == 'restore_production':
            self.restore_production_db(file_name)
        elif action == 'store':
            self.store(file_name)
        elif action == 'pull':
            self.pull()
        elif action == 'push':
            self.push()
        else:
            self.stdout.write(self.style.ERROR(f'{action} is not a valid argument'))

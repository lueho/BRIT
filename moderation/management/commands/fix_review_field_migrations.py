from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    """
    Management command to add the review workflow fields to database tables for models that inherit from UserCreatedObject.
    
    This command:
    1. Identifies all tables with publication_status field
    2. Adds the required fields (submitted_at, approved_at, approved_by_id) if they don't exist
    3. Creates indexes on publication_status 
    
    Use this for fixing migration issues with the review workflow fields.
    """
    
    help = "Fix missing review workflow fields in database tables"
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report issues without fixing them',
        )
    
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode. No changes will be made.'))
        
        # Check for transactions in error state
        with connection.cursor() as cursor:
            # Try to roll back any failed transaction
            try:
                cursor.execute("ROLLBACK;")
                self.stdout.write(self.style.SUCCESS("Successfully reset transaction state."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error resetting transaction: {e}"))
        
        # Get a list of all tables
        with connection.cursor() as cursor:
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            tables = [row[0] for row in cursor.fetchall()]
            
            self.stdout.write(f"Found {len(tables)} tables in database.")
            
            # For each table, check if it has publication_status column
            for table in tables:
                try:
                    cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'publication_status'")
                    has_publication_status = cursor.fetchone() is not None
                    
                    if has_publication_status:
                        self.stdout.write(f"Table {table} has publication_status field.")
                        
                        # Check for submitted_at field
                        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'submitted_at'")
                        has_submitted_at = cursor.fetchone() is not None
                        
                        # Check for approved_at field
                        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'approved_at'")
                        has_approved_at = cursor.fetchone() is not None
                        
                        # Check for approved_by_id field
                        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' AND column_name = 'approved_by_id'")
                        has_approved_by = cursor.fetchone() is not None
                        
                        # Report and fix missing columns
                        if not has_submitted_at:
                            self.stdout.write(self.style.WARNING(f"Table {table} is missing submitted_at field."))
                            if not dry_run:
                                try:
                                    cursor.execute(f"""
                                    ALTER TABLE "{table}" 
                                    ADD COLUMN "submitted_at" timestamp with time zone NULL
                                    """)
                                    self.stdout.write(self.style.SUCCESS(f"Added submitted_at to {table}."))
                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(f"Error adding submitted_at to {table}: {e}"))
                                    
                        if not has_approved_at:
                            self.stdout.write(self.style.WARNING(f"Table {table} is missing approved_at field."))
                            if not dry_run:
                                try:
                                    cursor.execute(f"""
                                    ALTER TABLE "{table}" 
                                    ADD COLUMN "approved_at" timestamp with time zone NULL
                                    """)
                                    self.stdout.write(self.style.SUCCESS(f"Added approved_at to {table}."))
                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(f"Error adding approved_at to {table}: {e}"))
                                    
                        if not has_approved_by:
                            self.stdout.write(self.style.WARNING(f"Table {table} is missing approved_by_id field."))
                            if not dry_run:
                                try:
                                    # Get the actual auth user table
                                    auth_user_table = 'auth_user'  # Default Django user table
                                    cursor.execute(f"""
                                    ALTER TABLE "{table}" 
                                    ADD COLUMN "approved_by_id" integer NULL
                                    REFERENCES "{auth_user_table}" ("id") 
                                    ON DELETE RESTRICT
                                    """)
                                    self.stdout.write(self.style.SUCCESS(f"Added approved_by_id to {table}."))
                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(f"Error adding approved_by_id to {table}: {e}"))
                        
                        # Add index on publication_status if it doesn't exist
                        cursor.execute(f"SELECT indexname FROM pg_indexes WHERE tablename = '{table}' AND indexname LIKE '%publication_status%'")
                        has_index = cursor.fetchone() is not None
                        
                        if not has_index:
                            self.stdout.write(self.style.WARNING(f"Table {table} is missing index on publication_status."))
                            if not dry_run:
                                try:
                                    cursor.execute(f"""
                                    CREATE INDEX IF NOT EXISTS "{table}_publication_status_idx" 
                                    ON "{table}" ("publication_status")
                                    """)
                                    self.stdout.write(self.style.SUCCESS(f"Added index on publication_status to {table}."))
                                except Exception as e:
                                    self.stdout.write(self.style.ERROR(f"Error adding index to {table}: {e}"))
                                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error processing table {table}: {e}"))
        
        self.stdout.write(self.style.SUCCESS("Finished checking for missing review workflow fields."))

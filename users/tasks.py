from celery import shared_task
from django.core.management import call_command


@shared_task
def cleanup_expired_registrations():
    """Delete accounts whose activation key expired without being used."""
    call_command("cleanupregistration")

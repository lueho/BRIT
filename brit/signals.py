from django.core.management import call_command
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def populate_initial_data(sender, **kwargs):
    call_command("ensure_initial_data")

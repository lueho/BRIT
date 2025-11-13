from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def populate_initial_data(sender, **kwargs):
    # Initialize the file export registry after migrations are complete
    pass

    # call_command("ensure_initial_data")

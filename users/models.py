from django.contrib.auth.models import Group, User
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def add_new_user_to_group_registered(sender, instance, created, **kwargs):
    if created:
        group, _ = Group.objects.get_or_create(name='registered')
        instance.groups.add(group)
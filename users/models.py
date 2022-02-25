import os

from django.contrib.auth.models import Group, User
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=User)
def add_new_user_to_group_registered(sender, instance, created, **kwargs):
    if created:
        instance.groups.add(Group.objects.get(name='registered'))


def get_default_owner():
    return User.objects.get(username=os.environ.get('ADMIN_USERNAME'))

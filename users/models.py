from django.contrib.auth.models import Group, User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
import os


@receiver(post_save, sender=User)
def add_new_user_to_group_registered(sender, instance, created, **kwargs):
    if created:
        instance.groups.add(Group.objects.get(name='registered'))


def get_default_owner():
    return User.objects.get(username=os.environ.get('ADMIN_USERNAME'))


class InitialUsersManager(models.Manager):
    STANDARD_OWNER_NAME = 'flexibi'

    def initialize(self):
        standard_owner, created = User.objects.get_or_create(username=self.STANDARD_OWNER_NAME)
        return super().create(standard_owner=standard_owner)

    @property
    def get(self):
        if not super().first():
            return self.initialize()
        else:
            return super().first()


class ReferenceUsers(models.Model):
    standard_owner = models.ForeignKey(User, on_delete=models.PROTECT)

    objects = InitialUsersManager()

    # class Meta:
    #     db_table = 'initial_users'

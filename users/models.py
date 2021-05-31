from django.contrib.auth.models import User
from django.db import models


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

from ambient_toolbox.models import CommonInfo
from django.contrib.auth.models import Group, User
from django.db import models
from django.urls import exceptions, reverse

from users.models import get_default_owner


class CRUDUrlsMixin(models.Model):
    """
    Mixin that implements the convention of url pattern for CRUD operations.
    """

    class Meta:
        abstract = True

    # Use a class-level format string to avoid code repetition
    url_format = "{name_lower}-{action}{suffix}"

    @classmethod
    def get_url(cls, action, suffix="", **kwargs):
        """
        Construct a URL for the given model and action, with optional suffix and kwargs.
        """
        try:
            url_name = cls.url_format.format(
                name_lower=cls.__name__.lower(),
                action=action,
                suffix=suffix,
            )
            return reverse(url_name, kwargs=kwargs)
        except exceptions.NoReverseMatch:
            return None

    @classmethod
    def list_url(cls):
        return cls.get_url("list")

    @classmethod
    def modal_list_url(cls):
        return cls.get_url("list", suffix="-modal")

    @classmethod
    def options_list_url(cls):
        return cls.get_url("options")

    @classmethod
    def create_url(cls):
        return cls.get_url("create")

    @classmethod
    def modal_create_url(cls):
        return cls.get_url("create", suffix="-modal")

    @property
    def detail_url(self):
        return self.get_url("detail", pk=self.pk)

    @property
    def modal_detail_url(self):
        return self.get_url("detail", suffix="-modal", pk=self.pk)

    def get_absolute_url(self):
        return self.detail_url

    @property
    def update_url(self):
        return self.get_url("update", pk=self.pk)

    @property
    def modal_update_url(self):
        return self.get_url("update", suffix="-modal", pk=self.pk)

    @property
    def delete_url(self):
        return self.get_url("delete", pk=self.pk)

    @property
    def modal_delete_url(self):
        return self.get_url("delete", suffix="-modal", pk=self.pk)


def get_default_owner_pk():
    return get_default_owner().pk


STATUS_CHOICES = (
        ('private', 'Private'),
        ('review', 'Under Review'),
        ('published', 'Published'),
    )


class OwnedObjectModel(CRUDUrlsMixin, CommonInfo):
    owner = models.ForeignKey(User, on_delete=models.PROTECT, default=get_default_owner_pk)
    visible_to_groups = models.ManyToManyField(Group)
    publication_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='private')

    class Meta:
        abstract = True


class NamedUserObjectModel(OwnedObjectModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

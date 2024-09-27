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


class OwnedObjectQuerySet(models.QuerySet):
    def published(self):
        return self.filter(publication_status='published')

    def owned_by_user(self, user):
        return self.filter(owner=user)

    def accessible_by_user(self, user):
        return self.filter(models.Q(owner=user) | models.Q(publication_status='published'))


class OwnedObjectManager(models.Manager):
    def get_queryset(self):
        return OwnedObjectQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()

    def owned_by_user(self, user):
        return self.get_queryset().owned_by_user(user)

    def accessible_by_user(self, user):
        return self.get_queryset().accessible_by_user(user)


class OwnedObjectModel(CRUDUrlsMixin, CommonInfo):
    owner = models.ForeignKey(User, on_delete=models.PROTECT, default=get_default_owner_pk)
    visible_to_groups = models.ManyToManyField(Group)
    publication_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='private')

    objects = OwnedObjectManager()

    class Meta:
        abstract = True


class NamedUserObjectModel(OwnedObjectModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ['name', 'id']

    def __str__(self):
        return self.name


class Redirect(models.Model):
    """
    Model representing a redirection from a short code to a full path URL.

    Attributes:
        short_code (models.CharField): A unique identifier for the redirect, typically a shortened URL path.
        full_path (models.TextField): The full URL path to which the short code should redirect.

    Methods:
        __str__(self): Returns a string representation of the Redirect instance, showing the short code and its corresponding full path.
    """

    short_code = models.CharField(max_length=50, unique=True)
    full_path = models.TextField()

    def __str__(self):
        return f"{self.short_code} -> {self.full_path}"

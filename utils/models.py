from ambient_toolbox.models import CommonInfo
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
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


class GlobalObject(CRUDUrlsMixin, CommonInfo):
    """
    Abstract base model for Global Objects.
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ['name']

    def __str__(self):
        return self.name


STATUS_CHOICES = (
    ('private', 'Private'),
    ('review', 'Under Review'),
    ('published', 'Published'),
)


class UserCreatedObjectQuerySet(models.QuerySet):
    def published(self):
        return self.filter(publication_status='published')

    def owned_by_user(self, user):
        return self.filter(owner=user)

    def reviewable_by_user(self, user):
        if self._is_moderator(user):
            return self.filter(publication_status='review')
        else:
            return self.none()

    def accessible_by_user(self, user):
        if self._is_moderator(user):
            return self.all()
        else:
            return self.filter(
                Q(owner=user) |
                Q(publication_status='published') |
                Q(publication_status='review', owner=user)
            )

    def _is_moderator(self, user):
        """
        Determines if the user has moderation permissions for the model.
        Assumes that a permission named 'can_moderate_<modelname>' exists.
        """
        model_name = self.model._meta.model_name
        perm_codename = f'can_moderate_{model_name}'
        app_label = self.model._meta.app_label
        return user.is_staff or user.has_perm(f'{app_label}.{perm_codename}')


class UserCreatedObjectManager(models.Manager):
    def get_queryset(self):
        return UserCreatedObjectQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()

    def owned_by_user(self, user):
        return self.get_queryset().owned_by_user(user)

    def reviewable_by_user(self, user):
        return self.get_queryset().reviewable_by_user(user)

    def accessible_by_user(self, user):
        return self.get_queryset().accessible_by_user(user)


class UserCreatedObject(CRUDUrlsMixin, CommonInfo):
    owner = models.ForeignKey(User, on_delete=models.PROTECT, default=get_default_owner_pk)
    publication_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='private')

    objects = UserCreatedObjectManager()

    class Meta:
        abstract = True

    def register_for_review(self):
        if self.publication_status != 'private':
            raise ValidationError("Only private objects can be registered for review.")
        self.publication_status = 'review'
        self.save()
        # TODO: Implement notification to moderators

    def withdraw_from_review(self):
        if self.publication_status != 'review':
            raise ValidationError("Only objects in review can be withdrawn.")
        self.publication_status = 'private'
        self.save()
        # TODO: Implement notification to moderators

    def approve(self):
        if self.publication_status != 'review':
            raise ValidationError("Only objects in review can be approved.")
        self.publication_status = 'published'
        self.save()
        # TODO: Implement notification to the owner

    def reject(self):
        if self.publication_status != 'review':
            raise ValidationError("Only objects in review can be rejected.")
        self.publication_status = 'private'
        self.save()
        # TODO: Implement notification to the owner


class NamedUserCreatedObject(UserCreatedObject):
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

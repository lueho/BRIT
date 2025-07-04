from ambient_toolbox.models import CommonInfo
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from ..models import CRUDUrlsMixin


def get_default_owner():
    """
    Returns the default owner User instance, using DEFAULT_OBJECT_OWNER_USERNAME or ADMIN_USERNAME.
    Raises RuntimeError if the user does not exist.
    """
    username = getattr(settings, "DEFAULT_OBJECT_OWNER_USERNAME", None)
    if not username:
        username = getattr(settings, "ADMIN_USERNAME", None)
    if not username:
        raise RuntimeError(
            "Neither DEFAULT_OBJECT_OWNER_USERNAME in settings nor ADMIN_USERNAME env var is set."
        )
    try:
        return User.objects.get(username=username)
    except User.DoesNotExist:
        raise RuntimeError(
            f"Default owner user '{username}' does not exist. Run ensure_initial_data."
        )


def get_default_owner_pk():
    return get_default_owner().pk


STATUS_CHOICES = (
    ("private", "Private"),
    ("review", "Under Review"),
    ("published", "Published"),
)


class GlobalObject(CRUDUrlsMixin, CommonInfo):
    """
    Abstract base model for Global Objects.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserCreatedObjectQuerySet(models.QuerySet):
    def published(self):
        return self.filter(publication_status=UserCreatedObject.STATUS_PUBLISHED)

    def owned_by_user(self, user):
        return self.filter(owner=user)

    def reviewable_by_user(self, user):
        if self._is_moderator(user):
            return self.filter(publication_status=UserCreatedObject.STATUS_REVIEW)
        else:
            return self.none()

    def in_review(self):
        return self.filter(publication_status=UserCreatedObject.STATUS_REVIEW)

    def accessible_by_user(self, user):
        if self._is_moderator(user):
            return self.all()
        else:
            return self.filter(
                Q(owner=user)
                | Q(publication_status=UserCreatedObject.STATUS_PUBLISHED)
                | Q(publication_status=UserCreatedObject.STATUS_REVIEW, owner=user)
            )

    def _is_moderator(self, user):
        """
        Determines if the user has moderation permissions for the model.
        Assumes that a permission named 'can_moderate_<modelname>' exists.
        """
        model_name = self.model._meta.model_name
        perm_codename = f"can_moderate_{model_name}"
        app_label = self.model._meta.app_label
        return user.is_staff or user.has_perm(f"{app_label}.{perm_codename}")


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
    STATUS_PRIVATE = "private"
    STATUS_REVIEW = "review"
    STATUS_PUBLISHED = "published"
    STATUS_ARCHIVED = "archived"

    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, default=get_default_owner_pk
    )
    publication_status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PRIVATE
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    objects = UserCreatedObjectManager()

    user_created = True

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["publication_status"]),
        ]

    def submit_for_review(self):
        """
        Submit this object for review. Transitions from private to review status.
        Sets submitted_at timestamp and clears approval fields if previously set.
        """
        if self.publication_status != self.STATUS_PRIVATE:
            raise ValidationError("Only private objects can be submitted for review.")
        self.publication_status = self.STATUS_REVIEW
        from django.utils import timezone

        self.submitted_at = timezone.now()
        self.approved_at = None
        self.approved_by = None
        self.save()
        # TODO: Implement notification to moderators
        return True

    def register_for_review(self):
        # Backward compatibility shim
        return self.submit_for_review()

    def withdraw_from_review(self):
        if self.publication_status != self.STATUS_REVIEW:
            raise ValidationError("Only objects in review can be withdrawn.")
        self.publication_status = self.STATUS_PRIVATE
        self.submitted_at = None
        self.save()
        # TODO: Implement notification to moderators

    def approve(self, user=None):
        """
        Approve this object, transitioning from review to published.
        Sets approved_at and approved_by.
        """
        if self.publication_status != self.STATUS_REVIEW:
            raise ValidationError("Only objects in review can be approved.")
        self.publication_status = self.STATUS_PUBLISHED
        from django.utils import timezone

        self.approved_at = timezone.now()
        if user is not None:
            self.approved_by = user
        self.save()
        # TODO: Implement notification to the owner

    def reject(self):
        if self.publication_status != self.STATUS_REVIEW:
            raise ValidationError("Only objects in review can be rejected.")
        self.publication_status = self.STATUS_PRIVATE
        self.submitted_at = None
        self.approved_at = None
        self.approved_by = None
        self.save()
        # TODO: Implement notification to the owner

    def archive(self):
        if self.publication_status != self.STATUS_PUBLISHED:
            raise ValidationError("Only published objects can be archived.")
        self.publication_status = self.STATUS_ARCHIVED
        self.save()
        # TODO: Implement notification to the owner

    @property
    def is_private(self):
        return self.publication_status == self.STATUS_PRIVATE

    @property
    def is_in_review(self):
        return self.publication_status == self.STATUS_REVIEW

    @property
    def is_published(self):
        return self.publication_status == self.STATUS_PUBLISHED

    @property
    def is_archived(self):
        return self.publication_status == self.STATUS_ARCHIVED

    @property
    def verbose_name(self):
        return self._meta.verbose_name


class NamedUserCreatedObject(UserCreatedObject):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ["name", "id"]

    def __str__(self):
        return self.name

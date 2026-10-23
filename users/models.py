from django.contrib.auth.models import Group, User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """Per-user preferences, created lazily on first write."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    review_notifications = models.BooleanField(
        default=True,
        help_text=(
            "E-mails about review activity on objects the user owns or commented on."
        ),
    )

    def __str__(self):
        return f"Profile of {self.user}"


@receiver(post_save, sender=User)
def add_new_user_to_group_registered(sender, instance, created, **kwargs):
    if created:
        group, _ = Group.objects.get_or_create(name="registered")
        instance.groups.add(group)

from django.db import models


class AppPermission(models.Model):
    """
    AppPermission model for temporary permission management in the mock phase.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_app_feature", "Can access the app feature"),
        ]

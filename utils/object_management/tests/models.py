from django.db import models


class TestGlobalObject(models.Model):
    """
    Concrete dummy of GlobalObject for testing purposes.
    """

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField()

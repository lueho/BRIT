from django.db import models

from ..models import GlobalObject


class TestGlobalObject(GlobalObject):
    """
    Concrete implementation of GlobalObject for testing purposes.
    """
    pass


class DummyModel(models.Model):
    test_field = models.FloatField(null=True)

    def __str__(self):
        return str(self.test_field)

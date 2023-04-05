from django.db import models


class DummyModel(models.Model):
    test_field = models.FloatField(null=True)

    def __str__(self):
        return str(self.test_field)

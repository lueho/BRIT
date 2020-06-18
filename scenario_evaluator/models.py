from django.db import models

from scenario_builder.models import Scenario


class RunningTask(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    uuid = models.UUIDField(primary_key=False)

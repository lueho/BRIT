from django.db import models

from scenario_builder.models import InventoryAlgorithm, Scenario


class RunningTask(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    algorithm = models.ForeignKey(InventoryAlgorithm, on_delete=models.CASCADE, null=True)
    uuid = models.UUIDField(primary_key=False)

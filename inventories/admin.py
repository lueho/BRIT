from django.contrib import admin

from .models import (Algorithm, InventoryAmountShare, Parameter, ParameterValue, Scenario, ScenarioConfiguration,
                     ScenarioStatus)

admin.site.register(Algorithm)
admin.site.register(Parameter)
admin.site.register(ParameterValue)
admin.site.register(Scenario)
admin.site.register(ScenarioConfiguration)
admin.site.register(ScenarioStatus)
admin.site.register(InventoryAmountShare)

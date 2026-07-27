from django.apps import AppConfig


class PopulationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "maps.population"
    label = "population"
    verbose_name = "Population"

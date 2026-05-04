from django.apps import AppConfig


class MaterialsConfig(AppConfig):
    name = "materials"

    def ready(self):
        import materials.exports  # noqa: F401

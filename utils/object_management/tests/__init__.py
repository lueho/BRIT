from django.apps import AppConfig, apps


# https://code.djangoproject.com/ticket/7835
def setup_test_app(package, label=None):
    """
    Setup a Django test app for the provided package to allow test models
    tables to be created if the containing app has migrations.

    This function should be called from app.tests __init__ module and pass
    along __package__.
    """
    app_config = AppConfig.create(package)
    app_config.apps = apps
    if label is None:
        containing_app_config = apps.get_containing_app_config(package)
        label = f"{containing_app_config.label}_tests"
    if label in apps.app_configs:
        raise ValueError(f"There's already an app registered with the '{label}' label.")
    app_config.label = label
    apps.app_configs[app_config.label] = app_config
    app_config.import_models()
    apps.clear_cache()


setup_test_app(__package__)

from django.db import migrations


def seed_settings(apps, schema_editor):
    model = apps.get_model("waste_atlas", "WasteAtlasRenderingSettings")
    model.objects.get_or_create(pk=1)


def unseed_settings(apps, schema_editor):
    model = apps.get_model("waste_atlas", "WasteAtlasRenderingSettings")
    model.objects.filter(pk=1).delete()


class Migration(migrations.Migration):
    dependencies = [("waste_atlas", "0006_wasteatlasrenderingsettings")]

    operations = [migrations.RunPython(seed_settings, unseed_settings)]

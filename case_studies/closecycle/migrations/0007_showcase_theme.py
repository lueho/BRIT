from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("closecycle", "0006_showcase_geom")]

    operations = [
        migrations.AddField(
            model_name="showcase",
            name="theme",
            field=models.CharField(
                blank=True,
                choices=[
                    ("apple_chain", "Apple Chain"),
                    ("greenhouses", "Greenhouses"),
                    ("nature_conservation", "Nature Conservation"),
                    ("tree_cultivation", "Tree Cultivation"),
                    ("municipalities_farms", "Municipalities and Farms"),
                    ("food_crops", "Food Crops"),
                    ("biorefinery_modules", "Biorefinery Modules"),
                ],
                default="",
                db_default="",
                max_length=32,
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="WasteAtlasMapConfiguration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "key",
                    models.SlugField(
                        help_text=(
                            "Stable key referenced by the Waste Atlas page registry."
                        ),
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "configuration",
                    models.JSONField(
                        default=dict,
                        help_text=(
                            "JSON object passed to the Waste Atlas choropleth renderer."
                        ),
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Waste Atlas map configuration",
                "verbose_name_plural": "Waste Atlas map configurations",
                "ordering": ("key",),
            },
        )
    ]

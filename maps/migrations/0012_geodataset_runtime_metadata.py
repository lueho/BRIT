from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("maps", "0011_alter_regionproperty_options"),
    ]

    operations = [
        migrations.AlterField(
            model_name="geodataset",
            name="model_name",
            field=models.CharField(
                blank=True,
                choices=[
                    ("HamburgRoadsideTrees", "HamburgRoadsideTrees"),
                    ("HamburgGreenAreas", "HamburgGreenAreas"),
                    ("NantesGreenhouses", "NantesGreenhouses"),
                    ("NutsRegion", "NutsRegion"),
                    ("WasteCollection", "WasteCollection"),
                ],
                max_length=56,
                null=True,
            ),
        ),
        migrations.CreateModel(
            name="GeoDatasetRuntimeConfiguration",
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
                    "backend_type",
                    models.CharField(
                        choices=[
                            ("legacy_model", "Legacy model"),
                            ("django_model", "Django model"),
                            ("local_relation", "Local relation"),
                        ],
                        default="legacy_model",
                        max_length=32,
                    ),
                ),
                ("runtime_model_name", models.CharField(blank=True, max_length=100)),
                ("schema_name", models.CharField(blank=True, max_length=100)),
                ("relation_name", models.CharField(blank=True, max_length=255)),
                ("geometry_column", models.CharField(blank=True, max_length=100)),
                ("primary_key_column", models.CharField(blank=True, max_length=100)),
                ("label_field", models.CharField(blank=True, max_length=100)),
                (
                    "features_api_basename",
                    models.CharField(blank=True, max_length=100),
                ),
                (
                    "dataset",
                    models.OneToOneField(
                        on_delete=models.CASCADE,
                        related_name="runtime_configuration",
                        to="maps.geodataset",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="GeoDatasetColumnPolicy",
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
                ("column_name", models.CharField(max_length=100)),
                ("display_label", models.CharField(blank=True, max_length=100)),
                ("is_visible", models.BooleanField(default=False)),
                ("is_filterable", models.BooleanField(default=False)),
                ("is_searchable", models.BooleanField(default=False)),
                ("is_exportable", models.BooleanField(default=False)),
                ("is_orderable", models.BooleanField(default=False)),
                (
                    "dataset",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="column_policies",
                        to="maps.geodataset",
                    ),
                ),
            ],
            options={"ordering": ["column_name"]},
        ),
        migrations.AddConstraint(
            model_name="geodatasetcolumnpolicy",
            constraint=models.UniqueConstraint(
                fields=("dataset", "column_name"),
                name="maps_geodatasetcolumnpolicy_dataset_column_unique",
            ),
        ),
    ]

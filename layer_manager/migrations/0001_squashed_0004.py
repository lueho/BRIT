import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    replaces = [
        ("layer_manager", "0001_initial"),
        ("layer_manager", "0002_unique_layer_field_name_data_type"),
        ("layer_manager", "0003_layer_staged"),
        ("layer_manager", "0004_layer_feedstock_material"),
    ]

    initial = True

    dependencies = [
        ("distributions", "0001_squashed_0004"),
        ("inventories", "0001_squashed_0008"),
        ("materials", "0001_squashed_0032"),
    ]

    operations = [
        migrations.CreateModel(
            name="DistributionSet",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "timestep",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="distributions.timestep",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="DistributionShare",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("average", models.FloatField()),
                (
                    "standard_deviation",
                    models.DecimalField(decimal_places=2, max_digits=5),
                ),
                (
                    "component",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="materials.materialcomponent",
                    ),
                ),
                (
                    "distribution_set",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="layer_manager.distributionset",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Layer",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=56)),
                ("geom_type", models.CharField(max_length=20)),
                ("table_name", models.CharField(max_length=200)),
                ("staged", models.BooleanField(default=False)),
                (
                    "algorithm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="inventories.inventoryalgorithm",
                    ),
                ),
                (
                    "feedstock",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="materials.material",
                    ),
                ),
                (
                    "sample_series",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="materials.sampleseries",
                    ),
                ),
                (
                    "scenario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="inventories.scenario",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="LayerAggregatedDistribution",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255, null=True)),
                (
                    "type",
                    models.CharField(
                        choices=[("seasonal", "seasonal")], max_length=255, null=True
                    ),
                ),
                (
                    "distribution",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="distributions.temporaldistribution",
                    ),
                ),
                (
                    "layer",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="layer_manager.layer",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="distributionset",
            name="aggregated_distribution",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="layer_manager.layeraggregateddistribution",
            ),
        ),
        migrations.CreateModel(
            name="LayerAggregatedValue",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=63)),
                ("value", models.FloatField()),
                (
                    "unit",
                    models.CharField(blank=True, default="", max_length=15, null=True),
                ),
                (
                    "layer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="layer_manager.layer",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="LayerField",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("field_name", models.CharField(max_length=63)),
                ("data_type", models.CharField(max_length=10)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("field_name", "data_type"),
                        name="unique_layer_field_name_data_type",
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="layer",
            name="layer_fields",
            field=models.ManyToManyField(to="layer_manager.layerfield"),
        ),
        migrations.AddConstraint(
            model_name="layer",
            constraint=models.UniqueConstraint(
                fields=("table_name",), name="unique table_name"
            ),
        ),
    ]

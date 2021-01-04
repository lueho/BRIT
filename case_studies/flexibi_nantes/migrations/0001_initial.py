# Generated by Django 3.0.7 on 2021-01-03 14:13

import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('scenario_builder', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NantesGreenhouses',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geom', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                ('id_exp', models.CharField(blank=True, max_length=255, null=True)),
                ('nom_exp', models.CharField(blank=True, max_length=255, null=True)),
                ('id_serre', models.CharField(blank=True, max_length=255, null=True)),
                ('lat', models.FloatField(blank=True, null=True)),
                ('lon', models.FloatField(blank=True, null=True)),
                ('surface_ha', models.FloatField(blank=True, max_length=255, null=True)),
                ('nb_cycles', models.IntegerField(blank=True, null=True)),
                ('culture_1', models.CharField(blank=True, max_length=20, null=True)),
                ('start_cycle_1', models.CharField(blank=True, max_length=20, null=True)),
                ('end_cycle_1', models.CharField(blank=True, max_length=20, null=True)),
                ('culture_2', models.CharField(blank=True, max_length=20, null=True)),
                ('start_cycle_2', models.CharField(blank=True, max_length=20, null=True)),
                ('end_cycle_2', models.CharField(blank=True, max_length=20, null=True)),
                ('culture_3', models.CharField(blank=True, max_length=20, null=True)),
                ('start_cycle_3', models.CharField(blank=True, max_length=20, null=True)),
                ('end_cycle_3', models.CharField(blank=True, max_length=20, null=True)),
                ('layer', models.CharField(blank=True, max_length=20, null=True)),
                ('heated', models.BooleanField(blank=True, null=True)),
                ('lighted', models.BooleanField(blank=True, null=True)),
                ('high_wire', models.BooleanField(blank=True, null=True)),
                ('above_ground', models.BooleanField(blank=True, null=True)),
            ],
            options={
                'db_table': 'gis_source_manager_nantesgreenhouses',
            },
        ),
        migrations.CreateModel(
            name='GreenhouseGrowthCycle',
            fields=[
                ('seasonaldistribution_ptr',
                 models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True,
                                      primary_key=True, serialize=False, to='scenario_builder.SeasonalDistribution')),
                ('cycle_number', models.IntegerField(default=1)),
                ('culture', models.CharField(blank=True, default='', max_length=255)),
                ('component', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                                to='scenario_builder.MaterialComponent')),
                ('material', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                               to='scenario_builder.Material')),
            ],
            bases=('scenario_builder.seasonaldistribution',),
        ),
        migrations.CreateModel(
            name='Greenhouse',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('heated', models.BooleanField(blank=True, null=True)),
                ('lighted', models.BooleanField(blank=True, null=True)),
                ('high_wire', models.BooleanField(blank=True, null=True)),
                ('above_ground', models.BooleanField(blank=True, null=True)),
                ('nb_cycles', models.IntegerField(null=True)),
                ('culture_1', models.CharField(blank=True, max_length=20, null=True)),
                ('culture_2', models.CharField(blank=True, max_length=20, null=True)),
                ('culture_3', models.CharField(blank=True, max_length=20, null=True)),
                ('growth_cycles', models.ManyToManyField(to='flexibi_nantes.GreenhouseGrowthCycle')),
                ('owner', models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE,
                                            to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

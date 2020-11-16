# Generated by Django 3.0.7 on 2020-11-10 16:02

import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('scenario_builder', '0003_seasonaldistribution'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='NantesGreenhouses',
                    fields=[
                        ('id',
                         models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
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

            ],
            database_operations=[]
        ),
        migrations.CreateModel(
            name='Greenhouse',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('heated', models.BooleanField(blank=True, null=True)),
                ('lighted', models.BooleanField(blank=True, null=True)),
                ('high_wire', models.BooleanField(blank=True, null=True)),
                ('above_ground', models.BooleanField(blank=True, null=True)),
                ('seasonal_distribution', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                                            to='scenario_builder.SeasonalDistribution')),
            ],
        ),
    ]

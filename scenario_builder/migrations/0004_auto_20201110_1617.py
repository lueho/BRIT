# Generated by Django 3.0.7 on 2020-11-10 16:17

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('scenario_builder', '0003_seasonaldistribution'),
    ]

    operations = [
        migrations.AddField(
            model_name='seasonaldistribution',
            name='start_stop',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(), null=True, size=None),
        ),
        migrations.AddField(
            model_name='seasonaldistribution',
            name='values',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), null=True, size=None),
        ),
    ]

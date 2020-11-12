# Generated by Django 3.0.7 on 2020-11-06 13:44

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('layer_manager', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LayerAggregatedDistribution',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, null=True)),
                ('type', models.CharField(choices=[('seasonal', 'seasonal')], max_length=255, null=True)),
                ('distribution',
                 django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), null=True, size=None)),
            ],
        ),
    ]

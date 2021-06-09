# Generated by Django 3.0.7 on 2021-02-17 19:54

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('scenario_builder', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RunningTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField()),
                ('algorithm', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='scenario_builder.InventoryAlgorithm')),
                ('scenario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scenario_builder.Scenario')),
            ],
        ),
    ]
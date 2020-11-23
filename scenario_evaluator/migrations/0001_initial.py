# Generated by Django 3.0.7 on 2020-11-23 13:27

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('scenario_builder', '0008_auto_20201123_1320'),
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

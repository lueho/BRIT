# Generated by Django 3.0.7 on 2021-05-10 12:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scenario_builder', '0003_auto_20210510_1208'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryalgorithmparametervalue',
            name='type',
            field=models.IntegerField(choices=[(1, 'Numeric'), (2, 'Selection')], default=1),
        ),
    ]
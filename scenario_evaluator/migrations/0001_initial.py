# Generated by Django 3.0.3 on 2020-05-19 11:36

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('scenario_builder', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScenarioResult',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('last_update', models.DateTimeField(auto_now=True)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('algorithm', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                                to='scenario_builder.InventoryAlgorithm')),
                ('scenario',
                 models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='scenario_builder.Scenario')),
            ],
        ),
        migrations.CreateModel(
            name='ScenarioResultAggregate',
            fields=[
                ('scenarioresult_ptr',
                 models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True,
                                      primary_key=True, serialize=False, to='scenario_evaluator.ScenarioResult')),
                ('name', models.CharField(max_length=56)),
                ('value', models.FloatField()),
                ('standard_deviation', models.FloatField(null=True)),
                ('unit', models.CharField(max_length=56, null=True)),
            ],
            bases=('scenario_evaluator.scenarioresult',),
        ),
        migrations.CreateModel(
            name='ScenarioResultLayer',
            fields=[
                ('scenarioresult_ptr',
                 models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True,
                                      primary_key=True, serialize=False, to='scenario_evaluator.ScenarioResult')),
                ('name', models.CharField(max_length=200)),
                ('base_class', models.CharField(max_length=200)),
                ('table_name', models.CharField(max_length=200, null=True, validators=[
                    django.core.validators.RegexValidator(code='invalid_parameter_name',
                                                          message='Invalid parameter function_name. Do not use space or                                                                special characters.',
                                                          regex='^\\w{1,28}$')])),
            ],
            bases=('scenario_evaluator.scenarioresult',),
        ),
    ]
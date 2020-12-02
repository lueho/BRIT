# Generated by Django 3.0.7 on 2020-12-01 09:29

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('scenario_builder', '0011_auto_20201123_1423'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaterialComponentGroupShare',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('component', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                                to='scenario_builder.MaterialComponent')),
                ('distribution', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                                   to='scenario_builder.SeasonalDistribution')),
                ('group', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                            to='scenario_builder.MaterialComponentGroup')),
                ('material', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                               to='scenario_builder.Material')),
                ('owner', models.ForeignKey(default=8, on_delete=django.db.models.deletion.CASCADE,
                                            to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

# Generated by Django 3.0.7 on 2020-10-10 07:03

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('scenario_builder', '0014_materialcomponent_owner'),
    ]

    operations = [
        migrations.AddField(
            model_name='materialcomponentgroup',
            name='owner',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE,
                                    to=settings.AUTH_USER_MODEL),
        ),
    ]

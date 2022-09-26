# Generated by Django 3.2.10 on 2022-09-24 14:35

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import brit.models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bibliography', '0012_auto_20220831_1349'),
    ]

    operations = [
        migrations.AlterField(
            model_name='author',
            name='owner',
            field=models.ForeignKey(default=brit.models.get_default_owner_pk,
                                    on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='licence',
            name='owner',
            field=models.ForeignKey(default=brit.models.get_default_owner_pk,
                                    on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='source',
            name='owner',
            field=models.ForeignKey(default=brit.models.get_default_owner_pk,
                                    on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
    ]

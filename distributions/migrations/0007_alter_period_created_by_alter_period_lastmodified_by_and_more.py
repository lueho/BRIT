# Generated by Django 4.0.10 on 2023-06-07 19:12

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('distributions', '0006_initial_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='period',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='period',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='temporaldistribution',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='temporaldistribution',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='timestep',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='timestep',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
    ]

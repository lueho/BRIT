# Generated by Django 4.0.10 on 2023-06-07 19:12

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('maps', '0007_catchment_parent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attribute',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='attribute',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='catchment',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='catchment',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='geodataset',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='geodataset',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='region',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='region',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='regionattributetextvalue',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='regionattributetextvalue',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='regionattributevalue',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='regionattributevalue',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='sfbsite',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='sfbsite',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
    ]

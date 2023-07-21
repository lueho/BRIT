# Generated by Django 4.0.10 on 2023-06-07 19:12

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('materials', '0005_alter_sampleseries_preview'),
    ]

    operations = [
        migrations.AlterField(
            model_name='basematerial',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='basematerial',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='composition',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='composition',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='materialcategory',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='materialcategory',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='materialcomponentgroup',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='materialcomponentgroup',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='materialproperty',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='materialproperty',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='materialpropertyvalue',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='materialpropertyvalue',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='sample',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='sample',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='sampleseries',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='sampleseries',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AlterField(
            model_name='weightshare',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AlterField(
            model_name='weightshare',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
    ]
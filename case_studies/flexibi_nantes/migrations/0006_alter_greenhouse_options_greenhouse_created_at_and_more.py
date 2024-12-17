# Generated by Django 5.1.1 on 2024-12-12 16:57

import django.db.models.deletion
import django.utils.timezone
import utils.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flexibi_nantes', '0005_remove_culture_visible_to_groups'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='greenhouse',
            options={'ordering': ['name', 'id']},
        ),
        migrations.AddField(
            model_name='greenhouse',
            name='created_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at'),
        ),
        migrations.AddField(
            model_name='greenhouse',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by'),
        ),
        migrations.AddField(
            model_name='greenhouse',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='greenhouse',
            name='lastmodified_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at'),
        ),
        migrations.AddField(
            model_name='greenhouse',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by'),
        ),
        migrations.AddField(
            model_name='greenhouse',
            name='publication_status',
            field=models.CharField(choices=[('private', 'Private'), ('review', 'Under Review'), ('published', 'Published')], default='private', max_length=10),
        ),
        migrations.AddField(
            model_name='greenhousegrowthcycle',
            name='created_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at'),
        ),
        migrations.AddField(
            model_name='greenhousegrowthcycle',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by'),
        ),
        migrations.AddField(
            model_name='greenhousegrowthcycle',
            name='lastmodified_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at'),
        ),
        migrations.AddField(
            model_name='greenhousegrowthcycle',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by'),
        ),
        migrations.AddField(
            model_name='greenhousegrowthcycle',
            name='publication_status',
            field=models.CharField(choices=[('private', 'Private'), ('review', 'Under Review'), ('published', 'Published')], default='private', max_length=10),
        ),
        migrations.AddField(
            model_name='growthshare',
            name='created_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at'),
        ),
        migrations.AddField(
            model_name='growthshare',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by'),
        ),
        migrations.AddField(
            model_name='growthshare',
            name='lastmodified_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at'),
        ),
        migrations.AddField(
            model_name='growthshare',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by'),
        ),
        migrations.AddField(
            model_name='growthshare',
            name='publication_status',
            field=models.CharField(choices=[('private', 'Private'), ('review', 'Under Review'), ('published', 'Published')], default='private', max_length=10),
        ),
        migrations.AlterField(
            model_name='greenhouse',
            name='name',
            field=models.CharField(default='Greenhouse', max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='greenhouse',
            name='owner',
            field=models.ForeignKey(default=utils.models.get_default_owner_pk, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='greenhousegrowthcycle',
            name='owner',
            field=models.ForeignKey(default=utils.models.get_default_owner_pk, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='growthshare',
            name='owner',
            field=models.ForeignKey(default=utils.models.get_default_owner_pk, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
    ]

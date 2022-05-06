# Generated by Django 3.2.10 on 2022-05-05 16:15

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('bibliography', '0003_author'),
    ]

    operations = [
        migrations.AddField(
            model_name='licence',
            name='created_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at'),
        ),
        migrations.AddField(
            model_name='licence',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bibliography_licence_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by'),
        ),
        migrations.AddField(
            model_name='licence',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='licence',
            name='lastmodified_at',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at'),
        ),
        migrations.AddField(
            model_name='licence',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bibliography_licence_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by'),
        ),
        migrations.AddField(
            model_name='licence',
            name='owner',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.PROTECT, to='auth.user'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='licence',
            name='visible_to_groups',
            field=models.ManyToManyField(to='auth.Group'),
        ),
    ]

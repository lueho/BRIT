# Generated by Django 3.2.10 on 2022-11-30 15:53

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import utils.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('distributions', '0003_auto_20220924_1435'),
    ]

    operations = [
        migrations.CreateModel(
            name='Period',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='distributions_period_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('distribution', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='distributions.temporaldistribution')),
                ('first_timestep', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='first_of_periods', to='distributions.timestep')),
                ('last_timestep', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='last_of_periods', to='distributions.timestep')),
                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='distributions_period_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                ('owner', models.ForeignKey(default=utils.models.get_default_owner_pk, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'unique_together': {('distribution', 'first_timestep', 'last_timestep')},
            },
        ),
    ]
# Generated by Django 3.2.8 on 2021-11-02 13:37

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bibliography', '0004_auto_20211031_2026'),
        ('inventories', '0012_alter_inventoryamountshare_timestep'),
    ]

    operations = [
        migrations.AlterField(
            model_name='catchment',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='catchment',
            name='region',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='inventories.region'),
        ),
        migrations.AlterField(
            model_name='geodataset',
            name='region',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='inventories.region'),
        ),
        migrations.AlterField(
            model_name='geodataset',
            name='sources',
            field=models.ManyToManyField(related_name='_inventories_geodataset_sources_+', to='bibliography.Source'),
        ),
        migrations.AlterField(
            model_name='sfbsite',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
    ]

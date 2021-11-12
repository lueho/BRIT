# Generated by Django 3.2.8 on 2021-11-11 16:08

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0022_auto_20211111_1549'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='catchment',
            name='region',
        ),
        migrations.AddField(
            model_name='catchment',
            name='parent_region',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='parent_region', to='maps.region'),
        ),
        migrations.AddField(
            model_name='catchment',
            name='regions',
            field=models.ManyToManyField(to='maps.Region'),
        ),
        migrations.AlterField(
            model_name='geodataset',
            name='model_name',
            field=models.CharField(choices=[('HamburgRoadsideTrees', 'HamburgRoadsideTrees'), ('HamburgGreenAreas', 'HamburgGreenAreas'), ('NantesGreenhouses', 'NantesGreenhouses'), ('NutsRegion', 'NutsRegion')], max_length=56, null=True),
        ),
    ]

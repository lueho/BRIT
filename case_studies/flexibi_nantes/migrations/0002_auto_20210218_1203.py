# Generated by Django 3.0.7 on 2021-02-18 12:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flexibi_nantes', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='nantesgreenhouses',
            name='culture_1',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='nantesgreenhouses',
            name='culture_2',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='nantesgreenhouses',
            name='culture_3',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='nantesgreenhouses',
            name='end_cycle_1',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='nantesgreenhouses',
            name='end_cycle_2',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='nantesgreenhouses',
            name='end_cycle_3',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='nantesgreenhouses',
            name='layer',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='nantesgreenhouses',
            name='start_cycle_1',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='nantesgreenhouses',
            name='start_cycle_2',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='nantesgreenhouses',
            name='surface_ha',
            field=models.FloatField(blank=True, null=True),
        ),
    ]

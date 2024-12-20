# Generated by Django 5.1.1 on 2024-11-09 13:31

from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('materials', '0011_alter_sample_preview_alter_sampleseries_preview'),
    ]

    operations = [
        migrations.AlterField(
            model_name='weightshare',
            name='average',
            field=models.DecimalField(decimal_places=10, default=Decimal('0.0'), max_digits=11),
        ),
        migrations.AlterField(
            model_name='weightshare',
            name='standard_deviation',
            field=models.DecimalField(decimal_places=10, default=Decimal('0.0'), max_digits=11),
        ),
    ]

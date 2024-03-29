# Generated by Django 3.2.10 on 2022-11-07 15:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0005_alter_sampleseries_preview'),
        ('soilcom', '0008_alter_collection_fee_system'),
    ]

    operations = [
        migrations.AddField(
            model_name='collection',
            name='samples',
            field=models.ManyToManyField(related_name='collections', to='materials.Sample'),
        ),
    ]

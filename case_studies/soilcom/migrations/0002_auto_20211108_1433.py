# Generated by Django 3.2.8 on 2021-11-08 14:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('soilcom', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='collectionsystem',
            options={'verbose_name': 'Waste Collection System'},
        ),
        migrations.AlterModelOptions(
            name='collector',
            options={'verbose_name': 'Waste Collector'},
        ),
    ]

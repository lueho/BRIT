# Generated by Django 4.2.8 on 2024-07-11 15:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('soilcom', '0030_aggregatedcollectionpropertyvalue_publication_status_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='collection',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='feesystem',
            options={'ordering': ['name']},
        ),
        migrations.AlterModelOptions(
            name='georeferencedwastecollection',
            options={'ordering': ['name']},
        ),
    ]

# Generated by Django 5.1.1 on 2024-10-01 12:27

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('soilcom', '0030_aggregatedcollectionpropertyvalue_publication_status_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='collection',
            options={'ordering': ['name', 'id']},
        ),
        migrations.AlterModelOptions(
            name='feesystem',
            options={'ordering': ['name', 'id']},
        ),
        migrations.AlterModelOptions(
            name='georeferencedwastecollection',
            options={'ordering': ['name', 'id']},
        ),
    ]

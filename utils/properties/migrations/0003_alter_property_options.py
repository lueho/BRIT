# Generated by Django 5.1.1 on 2024-10-01 12:27

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0002_property_publication_status_unit_publication_status'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='property',
            options={'ordering': ['name', 'id']},
        ),
    ]
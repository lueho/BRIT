# Generated by Django 4.2.8 on 2024-04-12 13:40

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0014_attribute_publication_status_and_more'),
        ('materials', '0009_alter_composition_fractions_of'),
        ('layer_manager', '0002_initial'),
        ('bibliography', '0017_author_publication_status_licence_publication_status_and_more'),
        ('inventories', '0009_rename_inventoryalgorithmparameter_parameter_and_more'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='InventoryAlgorithm',
            new_name='Algorithm',
        ),
    ]

# Generated by Django 3.0.7 on 2021-02-22 16:06

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('flexibi_nantes', '0010_remove_culture_residue'),
    ]

    operations = [
        migrations.RenameField(
            model_name='culture',
            old_name='feedstock',
            new_name='residue',
        ),
    ]

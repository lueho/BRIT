# Generated by Django 3.0.3 on 2020-05-20 11:52

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('layer_manager', '0007_auto_20200520_1326'),
    ]

    operations = [
        migrations.RenameField(
            model_name='layer',
            old_name='fields',
            new_name='layer_fields',
        ),
    ]
# Generated by Django 5.1.1 on 2024-11-16 19:49

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('inventories', '0007_alter_scenario_options'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='scenario',
            name='visible_to_groups',
        ),
    ]

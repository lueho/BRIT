# Generated by Django 5.1.1 on 2024-11-16 19:49

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('closecycle', '0002_alter_showcase_options'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='showcase',
            name='visible_to_groups',
        ),
    ]

# Generated by Django 5.1.1 on 2024-11-16 19:49

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('flexibi_nantes', '0004_alter_culture_options'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='culture',
            name='visible_to_groups',
        ),
    ]
# Generated by Django 5.1.1 on 2024-11-16 19:49

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('distributions', '0008_period_publication_status_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='period',
            name='visible_to_groups',
        ),
        migrations.RemoveField(
            model_name='temporaldistribution',
            name='visible_to_groups',
        ),
        migrations.RemoveField(
            model_name='timestep',
            name='visible_to_groups',
        ),
    ]
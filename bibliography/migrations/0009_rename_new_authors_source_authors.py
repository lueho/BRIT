# Generated by Django 3.2.10 on 2022-08-30 10:13

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bibliography', '0008_remove_source_authors'),
    ]

    operations = [
        migrations.RenameField(
            model_name='source',
            old_name='new_authors',
            new_name='authors',
        ),
    ]

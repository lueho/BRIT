# Generated by Django 4.2.8 on 2024-07-11 15:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bibliography', '0017_author_publication_status_licence_publication_status_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='licence',
            options={'ordering': ['name']},
        ),
    ]

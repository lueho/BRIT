# Generated by Django 3.2.10 on 2022-08-31 08:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bibliography', '0009_rename_new_authors_source_authors'),
    ]

    operations = [
        migrations.AlterField(
            model_name='author',
            name='first_names',
            field=models.CharField(blank=True, max_length=1023, null=True),
        ),
        migrations.AlterField(
            model_name='author',
            name='last_names',
            field=models.CharField(blank=True, max_length=1023, null=True),
        ),
    ]

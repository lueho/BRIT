# Generated by Django 4.2.8 on 2024-01-24 10:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('soilcom', '0022_collection_date'),
    ]

    operations = [
        migrations.RenameField(
            model_name='collection',
            old_name='date',
            new_name='valid_from',
        ),
        migrations.AddField(
            model_name='collection',
            name='valid_until',
            field=models.DateField(blank=True, null=True),
        ),
    ]
# Generated by Django 3.2.10 on 2022-08-31 13:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bibliography', '0010_auto_20220831_0847'),
    ]

    operations = [
        migrations.AlterField(
            model_name='licence',
            name='reference_url',
            field=models.URLField(blank=True, null=True),
        ),
    ]

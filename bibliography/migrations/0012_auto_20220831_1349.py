# Generated by Django 3.2.10 on 2022-08-31 13:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bibliography', '0011_alter_licence_reference_url'),
    ]

    operations = [
        migrations.AlterField(
            model_name='source',
            name='abbreviation',
            field=models.CharField(max_length=50),
        ),
        migrations.AlterField(
            model_name='source',
            name='title',
            field=models.CharField(max_length=500),
        ),
        migrations.AlterField(
            model_name='source',
            name='year',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]

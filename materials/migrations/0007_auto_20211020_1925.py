# Generated by Django 3.0.7 on 2021-10-11 13:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0006_auto_20211007_1350'),
    ]

    operations = [
        migrations.AddField(
            model_name='materialsettings',
            name='preview',
            field=models.ImageField(default='img/generic_material.jpg', upload_to=''),
        ),
        migrations.AddField(
            model_name='materialsettings',
            name='publish',
            field=models.BooleanField(default=False),
        ),
    ]
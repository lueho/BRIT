# Generated by Django 5.1.1 on 2024-11-03 09:17

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('materials', '0010_alter_materialcategory_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sample',
            name='preview',
            field=models.ImageField(blank=True, null=True, upload_to='materials_sample/'),
        ),
        migrations.AlterField(
            model_name='sampleseries',
            name='preview',
            field=models.ImageField(blank=True, null=True, upload_to='materials_sampleseries/'),
        ),
    ]

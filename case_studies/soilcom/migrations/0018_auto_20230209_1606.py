# Generated by Django 3.2.10 on 2023-02-09 16:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('materials', '0005_alter_sampleseries_preview'),
        ('soilcom', '0017_more_initial_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='wastestream',
            name='forbidden_materials',
            field=models.ManyToManyField(related_name='forbidden_in_waste_streams', to='materials.Material'),
        ),
        migrations.AlterField(
            model_name='wastestream',
            name='allowed_materials',
            field=models.ManyToManyField(related_name='allowed_in_waste_streams', to='materials.Material'),
        ),
    ]

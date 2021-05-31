# Generated by Django 3.0.7 on 2021-02-22 15:55

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('material_manager', '0002_auto_20210218_1640'),
        ('flexibi_nantes', '0008_auto_20210222_1010'),
    ]

    operations = [
        migrations.AddField(
            model_name='culture',
            name='feedstock',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    to='material_manager.MaterialSettings'),
        ),
    ]

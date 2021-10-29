# Generated by Django 3.2.8 on 2021-10-29 13:31

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('distributions', '0002_auto_20211029_1313'),
        ('layer_manager', '0002_auto_20210301_1944'),
    ]

    operations = [
        migrations.AlterField(
            model_name='distributionset',
            name='timestep',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='distributions.timestep'),
        ),
        migrations.AlterField(
            model_name='layeraggregateddistribution',
            name='distribution',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='distributions.temporaldistribution'),
        ),
    ]

# Generated by Django 3.2.10 on 2022-11-22 16:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0006_auto_20220924_1435'),
        ('soilcom', '0011_aggregatedcollectionpropertyvalue'),
    ]

    operations = [
        migrations.CreateModel(
            name='CollectionCatchment',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('maps.catchment',),
        ),
        migrations.AlterField(
            model_name='collection',
            name='catchment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='collections', to='maps.catchment'),
        ),
    ]

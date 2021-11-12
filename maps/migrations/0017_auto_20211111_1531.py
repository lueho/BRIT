# Generated by Django 3.2.8 on 2021-11-11 15:31

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0016_auto_20211111_1500'),
    ]

    operations = [
        migrations.CreateModel(
            name='GeoreferencedRegion',
            fields=[
                ('region_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, to='maps.region')),
                ('geopolygon_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='maps.geopolygon')),
            ],
            options={
                'abstract': False,
            },
            bases=('maps.geopolygon', 'maps.region'),
        ),
        migrations.RemoveField(
            model_name='nutsregion',
            name='fid',
        ),
    ]

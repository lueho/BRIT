# Generated by Django 3.2.8 on 2021-12-03 09:31

import django.contrib.gis.db.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='HamburgGreenAreas',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geom', django.contrib.gis.db.models.fields.MultiPolygonField(blank=True, null=True, srid=4326)),
                ('quelle_daten', models.CharField(blank=True, max_length=200, null=True)),
                ('identnummer', models.CharField(blank=True, max_length=63, null=True)),
                ('dgpkey', models.IntegerField(blank=True, null=True)),
                ('anlagenname', models.CharField(blank=True, max_length=200, null=True)),
                ('belegenheit', models.CharField(blank=True, max_length=200, null=True)),
                ('eigentum', models.CharField(blank=True, max_length=200, null=True)),
                ('bezirksnummer', models.IntegerField(blank=True, null=True)),
                ('ortsteil', models.IntegerField(blank=True, null=True)),
                ('flaeche_qm', models.FloatField(blank=True, null=True)),
                ('flaeche_ha', models.FloatField(blank=True, null=True)),
                ('gruenart', models.CharField(blank=True, max_length=200, null=True)),
                ('nutzcode', models.IntegerField(blank=True, null=True)),
                ('stand', models.CharField(blank=True, max_length=63, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='HamburgRoadsideTrees',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geom', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                ('baumid', models.IntegerField(blank=True, null=True)),
                ('gattung', models.CharField(blank=True, max_length=63, null=True)),
                ('gattung_latein', models.CharField(blank=True, max_length=63, null=True)),
                ('gattung_deutsch', models.CharField(blank=True, max_length=63, null=True)),
                ('art', models.CharField(blank=True, max_length=63, null=True)),
                ('art_latein', models.CharField(blank=True, max_length=63, null=True)),
                ('art_deutsch', models.CharField(blank=True, max_length=63, null=True)),
                ('sorte_latein', models.CharField(blank=True, max_length=63, null=True)),
                ('sorte_deutsch', models.CharField(blank=True, max_length=63, null=True)),
                ('pflanzjahr', models.IntegerField(blank=True, null=True)),
                ('pflanzjahr_portal', models.IntegerField(blank=True, null=True)),
                ('kronendurchmesser', models.IntegerField(blank=True, null=True)),
                ('stammumfang', models.IntegerField(blank=True, null=True)),
                ('strasse', models.CharField(blank=True, max_length=63, null=True)),
                ('hausnummer', models.CharField(blank=True, max_length=63, null=True)),
                ('ortsteil_nr', models.CharField(blank=True, max_length=63, null=True)),
                ('stadtteil', models.CharField(blank=True, max_length=63, null=True)),
                ('bezirk', models.CharField(blank=True, max_length=63, null=True)),
            ],
        ),
    ]

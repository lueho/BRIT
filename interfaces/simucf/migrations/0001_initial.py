# Generated by Django 5.1.7 on 2025-05-20 07:43

from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('materials', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InputMaterial',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('materials.sample',),
        ),
    ]

# Generated by Django 3.2.10 on 2022-07-13 08:47

from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('materials', '0003_auto_20220421_1220'),
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

# Generated by Django 5.1.1 on 2024-11-16 19:49

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('materials', '0012_alter_weightshare_average_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='basematerial',
            name='visible_to_groups',
        ),
        migrations.RemoveField(
            model_name='composition',
            name='visible_to_groups',
        ),
        migrations.RemoveField(
            model_name='materialcategory',
            name='visible_to_groups',
        ),
        migrations.RemoveField(
            model_name='materialcomponentgroup',
            name='visible_to_groups',
        ),
        migrations.RemoveField(
            model_name='materialproperty',
            name='visible_to_groups',
        ),
        migrations.RemoveField(
            model_name='materialpropertyvalue',
            name='visible_to_groups',
        ),
        migrations.RemoveField(
            model_name='sample',
            name='visible_to_groups',
        ),
        migrations.RemoveField(
            model_name='sampleseries',
            name='visible_to_groups',
        ),
        migrations.RemoveField(
            model_name='weightshare',
            name='visible_to_groups',
        ),
    ]

# Generated by Django 4.2.8 on 2024-03-26 11:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('distributions', '0007_alter_period_created_by_alter_period_lastmodified_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='period',
            name='publication_status',
            field=models.CharField(choices=[('private', 'Private'), ('review', 'Under Review'), ('published', 'Published')], default='private', max_length=10),
        ),
        migrations.AddField(
            model_name='temporaldistribution',
            name='publication_status',
            field=models.CharField(choices=[('private', 'Private'), ('review', 'Under Review'), ('published', 'Published')], default='private', max_length=10),
        ),
        migrations.AddField(
            model_name='timestep',
            name='publication_status',
            field=models.CharField(choices=[('private', 'Private'), ('review', 'Under Review'), ('published', 'Published')], default='private', max_length=10),
        ),
    ]
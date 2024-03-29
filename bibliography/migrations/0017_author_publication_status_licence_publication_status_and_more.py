# Generated by Django 4.2.8 on 2024-03-26 11:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bibliography', '0016_author_middle_names_author_preferred_citation_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='author',
            name='publication_status',
            field=models.CharField(choices=[('private', 'Private'), ('review', 'Under Review'), ('published', 'Published')], default='private', max_length=10),
        ),
        migrations.AddField(
            model_name='licence',
            name='publication_status',
            field=models.CharField(choices=[('private', 'Private'), ('review', 'Under Review'), ('published', 'Published')], default='private', max_length=10),
        ),
        migrations.AddField(
            model_name='source',
            name='publication_status',
            field=models.CharField(choices=[('private', 'Private'), ('review', 'Under Review'), ('published', 'Published')], default='private', max_length=10),
        ),
    ]

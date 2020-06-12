# Generated by Django 3.0.3 on 2020-05-19 16:29

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('layer_manager', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LayerField',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_name', models.CharField(max_length=63)),
                ('data_type', models.CharField(max_length=10)),
            ],
        ),
        migrations.AddField(
            model_name='layer',
            name='geom_type',
            field=models.CharField(default='point', max_length=20),
            preserve_default=False,
        ),
    ]
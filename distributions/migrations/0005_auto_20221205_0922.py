# Generated by Django 3.2.10 on 2022-12-05 09:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('distributions', '0004_period'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='timestep',
            options={'ordering': ['order']},
        ),
        migrations.AddField(
            model_name='timestep',
            name='order',
            field=models.IntegerField(default=90),
        ),
    ]

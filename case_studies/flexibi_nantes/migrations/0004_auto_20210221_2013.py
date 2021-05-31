# Generated by Django 3.0.7 on 2021-02-21 20:13

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('flexibi_dst', '0001_initial'),
        ('material_manager', '0002_auto_20210218_1640'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('flexibi_nantes', '0003_culture'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='greenhouse',
            name='culture_1',
        ),
        migrations.RemoveField(
            model_name='greenhouse',
            name='culture_2',
        ),
        migrations.RemoveField(
            model_name='greenhouse',
            name='culture_3',
        ),
        migrations.RemoveField(
            model_name='greenhouse',
            name='growth_cycles',
        ),
        migrations.RemoveField(
            model_name='greenhouse',
            name='nb_cycles',
        ),
        migrations.RemoveField(
            model_name='greenhousegrowthcycle',
            name='component',
        ),
        migrations.RemoveField(
            model_name='greenhousegrowthcycle',
            name='material',
        ),
        migrations.AddField(
            model_name='greenhousegrowthcycle',
            name='greenhouse',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='flexibi_nantes.Greenhouse'),
        ),
        migrations.AlterField(
            model_name='culture',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='culture',
            name='residue',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    to='material_manager.Material'),
        ),
        migrations.AlterField(
            model_name='greenhousegrowthcycle',
            name='culture',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='flexibi_nantes.Culture'),
        ),
        migrations.CreateModel(
            name='GrowthTimeStepSet',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group_settings', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                     to='material_manager.MaterialComponentGroupSettings')),
                ('owner', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                            to=settings.AUTH_USER_MODEL)),
                ('timestep', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='flexibi_dst.Timestep')),
            ],
        ),
        migrations.CreateModel(
            name='GrowthShare',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('average', models.FloatField(default=0.0)),
                ('standard_deviation', models.FloatField(default=0.0)),
                ('component', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                                to='material_manager.MaterialComponent')),
                ('owner', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                            to=settings.AUTH_USER_MODEL)),
                ('timestep_set', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                                   to='flexibi_nantes.GrowthTimeStepSet')),
            ],
        ),
    ]

# Generated by Django 3.2.8 on 2021-12-03 09:31

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('flexibi_nantes', '0001_initial'),
        ('distributions', '0001_initial'),
        ('materials', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='growthshare',
            name='component',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='materials.materialcomponent'),
        ),
        migrations.AddField(
            model_name='growthshare',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='growthshare',
            name='timestepset',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='flexibi_nantes.growthtimestepset'),
        ),
        migrations.AddField(
            model_name='greenhousegrowthcycle',
            name='culture',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='flexibi_nantes.culture'),
        ),
        migrations.AddField(
            model_name='greenhousegrowthcycle',
            name='greenhouse',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='flexibi_nantes.greenhouse'),
        ),
        migrations.AddField(
            model_name='greenhousegrowthcycle',
            name='group_settings',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='materials.materialcomponentgroupsettings'),
        ),
        migrations.AddField(
            model_name='greenhousegrowthcycle',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='greenhouse',
            name='owner',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE,
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='culture',
            name='owner',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='culture',
            name='residue',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    to='materials.materialsettings'),
        ),
        migrations.AddField(
            model_name='casestudybaseobjects',
            name='reference_distribution',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    to='distributions.temporaldistribution'),
        ),
    ]

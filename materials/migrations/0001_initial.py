# Generated by Django 3.2.10 on 2022-03-30 10:18

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('distributions', '0001_initial'),
        ('bibliography', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MaterialProperty',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('unit', models.CharField(max_length=63)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_materialproperty_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_materialproperty_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='MaterialPropertyValue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('average', models.FloatField()),
                ('standard_deviation', models.FloatField()),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_materialpropertyvalue_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_materialpropertyvalue_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='materials.materialproperty')),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SampleSeries',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('preview', models.ImageField(default='materials/img/generic_material.jpg', upload_to='')),
                ('publish', models.BooleanField(default=False)),
                ('standard', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_sampleseries_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_sampleseries_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('temporal_distributions', models.ManyToManyField(to='distributions.TemporalDistribution')),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Sample',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('taken_at', models.DateTimeField(blank=True, null=True)),
                ('preview', models.ImageField(blank=True, null=True, upload_to='')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_sample_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_sample_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('properties', models.ManyToManyField(to='materials.MaterialPropertyValue')),
                ('series', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='samples', to='materials.sampleseries')),
                ('sources', models.ManyToManyField(to='bibliography.Source')),
                ('timestep', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='samples', to='distributions.timestep')),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='MaterialComponentGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_materialcomponentgroup_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_materialcomponentgroup_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'verbose_name': 'material_component_group',
                'verbose_name_plural': 'groups',
                'unique_together': {('name', 'owner')},
            },
        ),
        migrations.CreateModel(
            name='MaterialCategory',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_materialcategory_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_materialcategory_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'verbose_name': 'Material Group',
            },
        ),
        migrations.CreateModel(
            name='Composition',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_composition_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='compositions', to='materials.materialcomponentgroup')),
                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_composition_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('sample', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='compositions', to='materials.sample')),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
                ('order', models.IntegerField(default=90)),
            ],
            options={
                'abstract': False,
                'ordering': ['order']
            },
        ),
        migrations.CreateModel(
            name='BaseMaterial',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('type', models.CharField(default='material', max_length=127)),
                ('categories', models.ManyToManyField(blank=True, to='materials.MaterialCategory')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_basematerial_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_basematerial_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'verbose_name': 'Material',
                'unique_together': {('name', 'owner')},
            },
        ),
        migrations.CreateModel(
            name='Material',
            fields=[
            ],
            options={
                'verbose_name': 'Material',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('materials.basematerial',),
        ),
        migrations.CreateModel(
            name='MaterialComponent',
            fields=[
            ],
            options={
                'verbose_name': 'component',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('materials.basematerial',),
        ),
        migrations.CreateModel(
            name='WeightShare',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('average', models.FloatField(default=0.0)),
                ('standard_deviation', models.FloatField(default=0.0)),
                ('composition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='materials.composition')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_weightshare_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='materials_weightshare_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
                ('component', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='materials.materialcomponent')),
            ],
            options={
                'abstract': False,
                'ordering': ['-average']
            },
        ),
        migrations.AddField(
            model_name='sampleseries',
            name='material',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='materials.material'),
        ),
        migrations.AddField(
            model_name='composition',
            name='fractions_of',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='materials.materialcomponent'),
        ),
    ]

# Generated by Django 3.2.8 on 2021-12-03 09:31

import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('maps', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('materials', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('bibliography', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Collection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at',
                 models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now,
                                                         verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('catchment', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                                to='maps.catchment')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='WasteCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at',
                 models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now,
                                                         verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name='soilcom_wastecategory_created',
                                                 to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by',
                 models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                   related_name='soilcom_wastecategory_lastmodified', to=settings.AUTH_USER_MODEL,
                                   verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'verbose_name': 'Waste Category',
                'verbose_name_plural': 'Waste categories',
            },
        ),
        migrations.CreateModel(
            name='WasteComponent',
            fields=[
            ],
            options={
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('materials.material',),
        ),
        migrations.CreateModel(
            name='WasteFlyer',
            fields=[
            ],
            options={
                'verbose_name': 'Waste Flyer',
                'proxy': True,
                'indexes': [],
                'constraints': [],
            },
            bases=('bibliography.source',),
        ),
        migrations.CreateModel(
            name='GeoreferencedWasteCollection',
            fields=[
                ('collection_ptr',
                 models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True,
                                      to='soilcom.collection')),
                ('geopolygon_ptr',
                 models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True,
                                      primary_key=True, serialize=False, to='maps.geopolygon')),
            ],
            options={
                'abstract': False,
            },
            bases=('maps.geopolygon', 'soilcom.collection'),
        ),
        migrations.CreateModel(
            name='WasteStream',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at',
                 models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now,
                                                         verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('allowed_materials', models.ManyToManyField(to='materials.Material')),
                (
                    'category',
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='soilcom.wastecategory')),
                ('composition', models.ManyToManyField(to='materials.MaterialSettings')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name='soilcom_wastestream_created',
                                                 to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by',
                 models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                   related_name='soilcom_wastestream_lastmodified', to=settings.AUTH_USER_MODEL,
                                   verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'verbose_name': 'Waste Stream',
            },
        ),
        migrations.CreateModel(
            name='Collector',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at',
                 models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now,
                                                         verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('website', models.URLField(blank=True, max_length=511, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name='soilcom_collector_created', to=settings.AUTH_USER_MODEL,
                                                 verbose_name='Created by')),
                ('lastmodified_by',
                 models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                   related_name='soilcom_collector_lastmodified', to=settings.AUTH_USER_MODEL,
                                   verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'verbose_name': 'Waste Collector',
            },
        ),
        migrations.CreateModel(
            name='CollectionSystem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at',
                 models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now,
                                                         verbose_name='Last modified at')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                                 related_name='soilcom_collectionsystem_created',
                                                 to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                ('lastmodified_by',
                 models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                   related_name='soilcom_collectionsystem_lastmodified', to=settings.AUTH_USER_MODEL,
                                   verbose_name='Last modified by')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('visible_to_groups', models.ManyToManyField(to='auth.Group')),
            ],
            options={
                'verbose_name': 'Waste Collection System',
            },
        ),
        migrations.AddField(
            model_name='collection',
            name='collection_system',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='soilcom.collectionsystem'),
        ),
        migrations.AddField(
            model_name='collection',
            name='collector',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='soilcom.collector'),
        ),
        migrations.AddField(
            model_name='collection',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='soilcom_collection_created', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Created by'),
        ),
        migrations.AddField(
            model_name='collection',
            name='flyer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='soilcom.wasteflyer'),
        ),
        migrations.AddField(
            model_name='collection',
            name='lastmodified_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                    related_name='soilcom_collection_lastmodified', to=settings.AUTH_USER_MODEL,
                                    verbose_name='Last modified by'),
        ),
        migrations.AddField(
            model_name='collection',
            name='owner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='collection',
            name='visible_to_groups',
            field=models.ManyToManyField(to='auth.Group'),
        ),
        migrations.AddField(
            model_name='collection',
            name='waste_stream',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                                    to='soilcom.wastestream'),
        ),
    ]

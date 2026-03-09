import django.contrib.gis.db.models.fields
import django.db.models.deletion
import django.utils.timezone
import utils.object_management.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('flexibi_nantes', '0004_alter_culture_publication_status_and_more'),
        ('distributions', '0004_alter_period_publication_status_and_more'),
        ('materials', '0007_merge_20260217_0951'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                        migrations.CreateModel(
                            name='NantesGreenhouses',
                            fields=[
                                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                                ('geom', django.contrib.gis.db.models.fields.PointField(blank=True, null=True, srid=4326)),
                                ('id_exp', models.CharField(blank=True, max_length=255, null=True)),
                                ('nom_exp', models.CharField(blank=True, max_length=255, null=True)),
                                ('id_serre', models.CharField(blank=True, max_length=255, null=True)),
                                ('lat', models.FloatField(blank=True, null=True)),
                                ('lon', models.FloatField(blank=True, null=True)),
                                ('surface_ha', models.FloatField(blank=True, null=True)),
                                ('nb_cycles', models.IntegerField(blank=True, null=True)),
                                ('culture_1', models.CharField(blank=True, max_length=255, null=True)),
                                ('start_cycle_1', models.CharField(blank=True, max_length=255, null=True)),
                                ('end_cycle_1', models.CharField(blank=True, max_length=255, null=True)),
                                ('culture_2', models.CharField(blank=True, max_length=255, null=True)),
                                ('start_cycle_2', models.CharField(blank=True, max_length=255, null=True)),
                                ('end_cycle_2', models.CharField(blank=True, max_length=255, null=True)),
                                ('culture_3', models.CharField(blank=True, max_length=255, null=True)),
                                ('start_cycle_3', models.CharField(blank=True, max_length=20, null=True)),
                                ('end_cycle_3', models.CharField(blank=True, max_length=255, null=True)),
                                ('layer', models.CharField(blank=True, max_length=255, null=True)),
                                ('heated', models.BooleanField(blank=True, null=True)),
                                ('lighted', models.BooleanField(blank=True, null=True)),
                                ('high_wire', models.BooleanField(blank=True, null=True)),
                                ('above_ground', models.BooleanField(blank=True, null=True)),
                            ],
                            options={
                                'db_table': 'flexibi_nantes_nantesgreenhouses',
                            },
                        ),
                        migrations.CreateModel(
                            name='CaseStudyBaseObjects',
                            fields=[
                                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                                ('reference_distribution', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='distributions.temporaldistribution')),
                            ],
                            options={
                                'db_table': 'flexibi_nantes_casestudybaseobjects',
                            },
                        ),
                        migrations.CreateModel(
                            name='Culture',
                            fields=[
                                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                                ('publication_status', models.CharField(choices=[('private', 'Private'), ('review', 'Review'), ('published', 'Published'), ('declined', 'Declined'), ('archived', 'Archived')], default='private', max_length=10)),
                                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                                ('approved_at', models.DateTimeField(blank=True, null=True)),
                                ('name', models.CharField(max_length=255)),
                                ('description', models.TextField(blank=True, null=True)),
                                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                                ('owner', models.ForeignKey(default=utils.object_management.models.get_default_owner_pk, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                                ('residue', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='materials.sampleseries')),
                            ],
                            options={
                                'db_table': 'flexibi_nantes_culture',
                                'ordering': ['name', 'id'],
                                'abstract': False,
                            },
                        ),
                        migrations.CreateModel(
                            name='Greenhouse',
                            fields=[
                                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                                ('publication_status', models.CharField(choices=[('private', 'Private'), ('review', 'Review'), ('published', 'Published'), ('declined', 'Declined'), ('archived', 'Archived')], default='private', max_length=10)),
                                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                                ('approved_at', models.DateTimeField(blank=True, null=True)),
                                ('name', models.CharField(max_length=255)),
                                ('description', models.TextField(blank=True, null=True)),
                                ('heated', models.BooleanField(blank=True, null=True)),
                                ('lighted', models.BooleanField(blank=True, null=True)),
                                ('high_wire', models.BooleanField(blank=True, null=True)),
                                ('above_ground', models.BooleanField(blank=True, null=True)),
                                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                                ('owner', models.ForeignKey(default=utils.object_management.models.get_default_owner_pk, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                            ],
                            options={
                                'db_table': 'flexibi_nantes_greenhouse',
                                'ordering': ['name', 'id'],
                                'abstract': False,
                            },
                        ),
                        migrations.CreateModel(
                            name='GreenhouseGrowthCycle',
                            fields=[
                                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                                ('publication_status', models.CharField(choices=[('private', 'Private'), ('review', 'Review'), ('published', 'Published'), ('declined', 'Declined'), ('archived', 'Archived')], default='private', max_length=10)),
                                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                                ('approved_at', models.DateTimeField(blank=True, null=True)),
                                ('cycle_number', models.IntegerField(default=1)),
                                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                                ('culture', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='greenhouses.culture')),
                                ('greenhouse', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='greenhouses.greenhouse')),
                                ('group_settings', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='materials.composition')),
                                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                                ('owner', models.ForeignKey(default=utils.object_management.models.get_default_owner_pk, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                            ],
                            options={
                                'db_table': 'flexibi_nantes_greenhousegrowthcycle',
                                'abstract': False,
                            },
                        ),
                        migrations.CreateModel(
                            name='GrowthTimeStepSet',
                            fields=[
                                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                                ('growth_cycle', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='greenhouses.greenhousegrowthcycle')),
                                ('owner', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                                ('timestep', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='distributions.timestep')),
                            ],
                            options={
                                'db_table': 'flexibi_nantes_growthtimestepset',
                            },
                        ),
                        migrations.CreateModel(
                            name='GrowthShare',
                            fields=[
                                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Created at')),
                                ('lastmodified_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now, verbose_name='Last modified at')),
                                ('publication_status', models.CharField(choices=[('private', 'Private'), ('review', 'Review'), ('published', 'Published'), ('declined', 'Declined'), ('archived', 'Archived')], default='private', max_length=10)),
                                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                                ('approved_at', models.DateTimeField(blank=True, null=True)),
                                ('average', models.FloatField(default=0.0)),
                                ('standard_deviation', models.FloatField(default=0.0)),
                                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
                                ('component', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='materials.materialcomponent')),
                                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Created by')),
                                ('lastmodified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_lastmodified', to=settings.AUTH_USER_MODEL, verbose_name='Last modified by')),
                                ('owner', models.ForeignKey(default=utils.object_management.models.get_default_owner_pk, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                                ('timestepset', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='greenhouses.growthtimestepset')),
                            ],
                            options={
                                'db_table': 'flexibi_nantes_growthshare',
                                'abstract': False,
                            },
                        ),
                        migrations.AddIndex(
                            model_name='greenhousegrowthcycle',
                            index=models.Index(fields=['publication_status'], name='flexibi_nan_publica_d66165_idx'),
                        ),
                        migrations.AddIndex(
                            model_name='growthshare',
                            index=models.Index(fields=['publication_status'], name='flexibi_nan_publica_3516d7_idx'),
                        ),
            ],
        )
    ]

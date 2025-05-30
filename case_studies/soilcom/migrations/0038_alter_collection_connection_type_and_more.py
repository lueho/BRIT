# Generated by Django 5.1.7 on 2025-05-07 13:15

from django.db import migrations, models


def migrate_connection_type(apps, schema_editor):
    Collection = apps.get_model('soilcom', 'Collection')
    # Migrate 'COMPULSORY' and 'compulsory' to 'MANDATORY'
    Collection.objects.filter(connection_type='COMPULSORY').update(connection_type='MANDATORY')
    Collection.objects.filter(connection_type='compulsory').update(connection_type='MANDATORY')
    Collection.objects.filter(connection_type='VOLUNTARY').update(connection_type=None)

class Migration(migrations.Migration):

    dependencies = [
        ('soilcom', '0037_alter_collection_connection_type_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collection',
            name='connection_type',
            field=models.CharField(blank=True, choices=[('MANDATORY', 'mandatory'), ('MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION', 'mandatory with exception for home composters'), ('VOLUNTARY', 'voluntary'), ('not_specified', 'not specified')], default=None, help_text="Indicates whether connection to the collection system is mandatory, voluntary, or not specified. Leave blank for never set; select 'not specified' for explicit user choice.", max_length=40, null=True, verbose_name='Connection type'),
        ),
        migrations.AlterField(
            model_name='collection',
            name='required_bin_capacity_reference',
            field=models.CharField(blank=True, choices=[('person', 'per person'), ('household', 'per household'), ('property', 'per property'), ('not_specified', 'not specified')], default=None, help_text='Defines the unit (person, household, property) for which the required bin capacity applies. Leave blank if not specified.', max_length=16, null=True, verbose_name='Reference unit for required bin capacity'),
        ),
        migrations.RunPython(migrate_connection_type, reverse_code=migrations.RunPython.noop),
    ]

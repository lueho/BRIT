from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("waste_collection", "0005_replace_access_control_with_bp_pap"),
    ]

    operations = [
        migrations.RenameField(
            model_name="collection",
            old_name="connection_type",
            new_name="participation_policy",
        ),
        migrations.AlterField(
            model_name="collection",
            name="participation_policy",
            field=models.CharField(
                blank=True,
                choices=[
                    ("MANDATORY", "mandatory"),
                    (
                        "MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION",
                        "mandatory with exception for home composters",
                    ),
                    ("VOLUNTARY", "voluntary"),
                    ("not_specified", "not specified"),
                ],
                default=None,
                help_text=(
                    "Indicates whether connection to the collection system is "
                    "mandatory, voluntary, or not specified. Leave blank for "
                    "never set; select 'not specified' for explicit user choice."
                ),
                max_length=40,
                null=True,
                verbose_name="Participation policy",
            ),
        ),
    ]

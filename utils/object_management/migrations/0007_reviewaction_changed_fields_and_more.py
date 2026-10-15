from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("object_management", "0006_alter_reviewaction_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="reviewaction",
            name="changed_fields",
            field=models.JSONField(blank=True, default=list, editable=False),
        ),
        migrations.AddField(
            model_name="reviewaction",
            name="content_revision",
            field=models.PositiveBigIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="reviewaction",
            name="action",
            field=models.CharField(
                choices=[
                    ("submitted", "Submitted"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("withdrawn", "Withdrawn"),
                    ("comment", "Comment"),
                    ("created", "Created"),
                    ("edited", "Edited"),
                    ("deleted", "Deleted"),
                ],
                max_length=20,
            ),
        ),
    ]

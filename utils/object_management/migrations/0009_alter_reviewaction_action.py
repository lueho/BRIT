from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("object_management", "0008_reviewaction_changed_fields_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reviewaction",
            name="action",
            field=models.CharField(
                choices=[
                    ("submitted", "Submitted"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("withdrawn", "Withdrawn"),
                    ("archived", "Archived"),
                    ("comment", "Comment"),
                    ("created", "Created"),
                    ("edited", "Edited"),
                    ("deleted", "Deleted"),
                ],
                max_length=20,
            ),
        ),
    ]

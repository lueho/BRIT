from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("object_management", "0006_merge_review_notification_mute"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="reviewaction",
            options={
                "ordering": ["-created_at", "-id"],
                "permissions": [
                    ("administer_objects", "Can administer user-created objects")
                ],
            },
        ),
    ]

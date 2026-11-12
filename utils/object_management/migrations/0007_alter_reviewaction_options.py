from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("object_management", "0001_squashed_0006"),
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

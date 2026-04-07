from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("urban_green_spaces", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelTable(
            name="hamburggreenareas",
            table="urban_green_spaces_hamburggreenareas",
        ),
    ]

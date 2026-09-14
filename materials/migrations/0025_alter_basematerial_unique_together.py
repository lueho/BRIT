from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("materials", "0024_sampleexternalrecord_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="basematerial",
            unique_together={("name", "owner", "type")},
        ),
    ]

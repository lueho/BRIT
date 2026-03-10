from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("soilcom", "0011_collection_inline_waste_fields"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="collection",
            name="waste_stream",
        ),
        migrations.DeleteModel(
            name="WasteStream",
        ),
    ]

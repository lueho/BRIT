from django.db import migrations, models


def map_types_to_new_vocabulary(apps, schema_editor):
    Source = apps.get_model("bibliography", "Source")
    Source.objects.filter(type="website").update(type="online")
    Source.objects.filter(type="custom").update(type="misc")


def map_types_to_old_vocabulary(apps, schema_editor):
    Source = apps.get_model("bibliography", "Source")
    Source.objects.filter(type="online").update(type="website")
    Source.objects.filter(type="misc").update(type="custom")


class Migration(migrations.Migration):
    dependencies = [
        (
            "bibliography",
            "0011_author_author_type_author_organization_abbreviation_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            map_types_to_new_vocabulary,
            reverse_code=map_types_to_old_vocabulary,
        ),
        migrations.AlterField(
            model_name="source",
            name="type",
            field=models.CharField(
                choices=[
                    ("article", "Journal article"),
                    ("book", "Book"),
                    ("incollection", "Book chapter"),
                    ("proceedings", "Conference proceedings"),
                    ("inproceedings", "Conference paper"),
                    ("report", "Report"),
                    ("thesis", "Thesis"),
                    ("preprint", "Preprint"),
                    ("dataset", "Dataset"),
                    ("standard", "Standard"),
                    ("patent", "Patent"),
                    ("online", "Online resource"),
                    ("periodical", "Periodical"),
                    ("misc", "Miscellaneous"),
                ],
                default="misc",
                max_length=255,
            ),
        ),
    ]

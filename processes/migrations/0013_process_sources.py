from django.db import migrations, models


def copy_reference_sources_to_process_sources(apps, schema_editor):
    Process = apps.get_model("processes", "Process")
    ProcessReference = apps.get_model("processes", "ProcessReference")
    through_model = Process.sources.through

    through_model.objects.bulk_create(
        [
            through_model(
                process_id=reference.process_id, source_id=reference.source_id
            )
            for reference in ProcessReference.objects.exclude(source_id__isnull=True)
            .order_by("process_id", "source_id")
            .distinct("process_id", "source_id")
        ],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("bibliography", "0010_author_contact_details"),
        ("processes", "0012_move_process_contact_details_to_authors"),
    ]

    operations = [
        migrations.AddField(
            model_name="process",
            name="sources",
            field=models.ManyToManyField(
                blank=True,
                help_text="Bibliography sources used by this process.",
                related_name="processes",
                to="bibliography.source",
            ),
        ),
        migrations.RunPython(
            copy_reference_sources_to_process_sources,
            migrations.RunPython.noop,
        ),
        migrations.DeleteModel(
            name="ProcessReference",
        ),
    ]

from django.db import migrations, models


def copy_author_to_authors(apps, schema_editor):
    Process = apps.get_model("processes", "Process")
    through_model = Process.authors.through
    through_model.objects.bulk_create(
        [
            through_model(process_id=process.id, author_id=process.author_id)
            for process in Process.objects.exclude(author_id__isnull=True).only(
                "id", "author_id"
            )
        ],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("bibliography", "0009_rename_source_bibtex_fields"),
        ("processes", "0010_process_image_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="process",
            name="authors",
            field=models.ManyToManyField(
                blank=True,
                help_text="Authors or contributors shown on the process detail page.",
                related_name="processes",
                to="bibliography.author",
            ),
        ),
        migrations.RunPython(copy_author_to_authors, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="process",
            name="author",
        ),
    ]

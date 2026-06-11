import django.db.models.deletion
from django.db import migrations, models


def copy_process_authors_and_sources(apps, schema_editor):
    Process = apps.get_model("processes", "Process")
    ProcessAuthor = apps.get_model("processes", "ProcessAuthor")
    ProcessSource = apps.get_model("processes", "ProcessSource")

    author_through = Process.authors.through
    source_through = Process.sources.through

    author_links = []
    current_process_id = None
    position = 0
    for link in author_through.objects.order_by("process_id", "id"):
        if link.process_id != current_process_id:
            current_process_id = link.process_id
            position = 0
        position += 1
        author_links.append(
            ProcessAuthor(
                process_id=link.process_id,
                author_id=link.author_id,
                position=position,
            )
        )
    ProcessAuthor.objects.bulk_create(author_links, ignore_conflicts=True)

    source_links = []
    current_process_id = None
    order = 0
    for link in source_through.objects.order_by("process_id", "id"):
        if link.process_id != current_process_id:
            current_process_id = link.process_id
            order = 0
        order += 1
        source_links.append(
            ProcessSource(
                process_id=link.process_id,
                source_id=link.source_id,
                order=order,
            )
        )
    ProcessSource.objects.bulk_create(source_links, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("bibliography", "0010_author_contact_details"),
        ("processes", "0013_process_sources"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessAuthor",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("position", models.PositiveIntegerField(default=1)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="process_author_links",
                        to="bibliography.author",
                    ),
                ),
                (
                    "process",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="process_authors",
                        to="processes.process",
                    ),
                ),
            ],
            options={
                "ordering": ["position", "id"],
            },
        ),
        migrations.CreateModel(
            name="ProcessSource",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "process",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="process_sources",
                        to="processes.process",
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="process_source_links",
                        to="bibliography.source",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(
            copy_process_authors_and_sources,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="process",
            name="authors",
        ),
        migrations.RemoveField(
            model_name="process",
            name="sources",
        ),
        migrations.AddField(
            model_name="process",
            name="authors",
            field=models.ManyToManyField(
                blank=True,
                help_text="Authors or contributors shown on the process detail page.",
                related_name="processes",
                through="processes.ProcessAuthor",
                to="bibliography.author",
            ),
        ),
        migrations.AddField(
            model_name="process",
            name="sources",
            field=models.ManyToManyField(
                blank=True,
                help_text="Bibliography sources used by this process.",
                related_name="processes",
                through="processes.ProcessSource",
                to="bibliography.source",
            ),
        ),
        migrations.AddConstraint(
            model_name="processauthor",
            constraint=models.UniqueConstraint(
                fields=("process", "author"),
                name="processes_processauthor_unique_author",
            ),
        ),
        migrations.AddConstraint(
            model_name="processsource",
            constraint=models.UniqueConstraint(
                fields=("process", "source"),
                name="processes_processsource_unique_source",
            ),
        ),
    ]

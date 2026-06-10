from django.db import migrations


def copy_process_contact_details_to_authors(apps, schema_editor):
    Process = apps.get_model("processes", "Process")
    Author = apps.get_model("bibliography", "Author")

    processes = (
        Process.objects.exclude(author_institution="")
        | Process.objects.exclude(contact_email="")
    ).distinct()

    for process in processes.prefetch_related("authors"):
        author_ids = [author.id for author in process.authors.all()]
        if not author_ids:
            continue

        if process.author_institution:
            Author.objects.filter(id__in=author_ids, institution="").update(
                institution=process.author_institution
            )
        if process.contact_email:
            Author.objects.filter(id__in=author_ids, contact_email="").update(
                contact_email=process.contact_email
            )


class Migration(migrations.Migration):
    dependencies = [
        ("bibliography", "0010_author_contact_details"),
        ("processes", "0011_process_authors"),
    ]

    operations = [
        migrations.RunPython(
            copy_process_contact_details_to_authors,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="process",
            name="author_institution",
        ),
        migrations.RemoveField(
            model_name="process",
            name="contact_email",
        ),
    ]

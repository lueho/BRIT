from django.db import migrations


def create_initial_data(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Source = apps.get_model('bibliography', 'Source')

    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type = ContentType.objects.get_for_model(Source)

    Permission = apps.get_model('auth', 'Permission')
    add_source_permission, _ = Permission.objects.get_or_create(codename='add_source', content_type=content_type)
    view_source_permission, _ = Permission.objects.get_or_create(codename='view_source', content_type=content_type)
    change_source_permission, _ = Permission.objects.get_or_create(codename='change_source', content_type=content_type)
    delete_source_permission, _ = Permission.objects.get_or_create(codename='delete_source', content_type=content_type)

    registered = Group.objects.get(name='registered')
    registered.permissions.add(add_source_permission)
    registered.permissions.add(view_source_permission)

    librarians, _ = Group.objects.get_or_create(name='librarians')
    librarians.permissions.add(add_source_permission)
    librarians.permissions.add(view_source_permission)
    librarians.permissions.add(change_source_permission)
    librarians.permissions.add(delete_source_permission)


class Migration(migrations.Migration):
    dependencies = [
        ('bibliography', '0001_initial'),
        ('users', '0002_initial_data')
    ]

    operations = [
        migrations.RunPython(create_initial_data)
    ]

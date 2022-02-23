from django.db import migrations


def create_initial_data(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    registered = Group.objects.get(name='registered')
    Permission = apps.get_model('auth', 'Permission')
    Source = apps.get_model('bibliography', 'Source')
    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type = ContentType.objects.get_for_model(Source)
    permission, _ = Permission.objects.get_or_create(codename='add_source', content_type=content_type)
    registered.permissions.add(permission)
    permission, _ = Permission.objects.get_or_create(codename='view_source', content_type=content_type)
    registered.permissions.add(permission)


class Migration(migrations.Migration):
    dependencies = [
        ('bibliography', '0001_initial'),
        ('users', '0002_initial_data')
    ]

    operations = [
        migrations.RunPython(create_initial_data)
    ]

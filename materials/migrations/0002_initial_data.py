from django.db import migrations

from users.models import get_default_owner


def create_initial_data(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    owner = User.objects.get(username=get_default_owner().username)
    MaterialComponentGroup = apps.get_model('materials', 'MaterialComponentGroup')
    group, _ = MaterialComponentGroup.objects.get_or_create(name='Total Material', owner=owner)
    MaterialComponent = apps.get_model('materials', 'MaterialComponent')
    component, _ = MaterialComponent.objects.get_or_create(name='Fresh Matter (FM)', owner=owner)

    Group = apps.get_model('auth', 'Group')
    Material = apps.get_model('materials', 'Material')

    ContentType = apps.get_model("contenttypes", "ContentType")
    content_type = ContentType.objects.get_for_model(Material)

    Permission = apps.get_model('auth', 'Permission')
    add_material, _ = Permission.objects.get_or_create(codename='add_material', content_type=content_type)
    view_material, _ = Permission.objects.get_or_create(codename='view_material', content_type=content_type)
    change_material, _ = Permission.objects.get_or_create(codename='change_material', content_type=content_type)
    delete_material, _ = Permission.objects.get_or_create(codename='delete_material', content_type=content_type)

    registered = Group.objects.get(name='registered')
    registered.permissions.add(view_material)
    registered.permissions.add(add_material)
    registered.save()


class Migration(migrations.Migration):
    dependencies = [
        ('materials', '0001_initial'),
        ('users', '0002_initial_data')
    ]

    operations = [
        migrations.RunPython(create_initial_data)
    ]

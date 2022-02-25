from django.db import migrations

from users.models import get_default_owner


def create_initial_data(apps, schema_editor):

    User = apps.get_model('auth', 'User')
    owner = User.objects.get(username=get_default_owner().username)
    MaterialComponentGroup = apps.get_model('materials', 'MaterialComponentGroup')
    group, _ = MaterialComponentGroup.objects.get_or_create(name='Total Material', owner=owner)
    MaterialComponent = apps.get_model('materials', 'MaterialComponent')
    component, _ = MaterialComponent.objects.get_or_create(name='Fresh Matter (FM)', owner=owner)


class Migration(migrations.Migration):
    dependencies = [
        ('materials', '0001_initial'),
        ('users', '0002_initial_data')
    ]

    operations = [
        migrations.RunPython(create_initial_data)
    ]

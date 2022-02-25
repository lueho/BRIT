from django.db import migrations

from users.models import get_default_owner


def create_initial_data(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    owner = User.objects.get(username=get_default_owner().username)

    TemporalDistribution = apps.get_model('distributions', 'TemporalDistribution')
    distribution, _ = TemporalDistribution.objects.get_or_create(name='Average', owner=owner)
    Timestep = apps.get_model('distributions', 'Timestep')
    timestep, _ = Timestep.objects.get_or_create(name='Average', distribution=distribution, owner=owner)


class Migration(migrations.Migration):
    dependencies = [
        ('distributions', '0001_initial'),
        ('users', '0002_initial_data')

    ]

    operations = [
        migrations.RunPython(create_initial_data)
    ]

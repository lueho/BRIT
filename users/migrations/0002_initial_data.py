import os
from django.db import migrations
from django.utils import timezone
from django.contrib.auth import get_user_model


def create_initial_data(apps, schema_editor):
    Group = apps.get_model('auth.Group')
    registered, _ = Group.objects.get_or_create(name='registered')

    User = get_user_model()
    try:
        superuser = User.objects.get(username=os.environ['ADMIN_USERNAME'])
    except User.DoesNotExist:
        superuser = User(
            is_active=True,
            is_superuser=True,
            is_staff=True,
            username=os.environ['ADMIN_USERNAME'],
            email=os.environ['ADMIN_EMAIL'],
            last_login=timezone.now(),
        )
        superuser.set_password(os.environ['ADMIN_PASSWORD'])
        superuser.save()

    superuser.groups.add(registered.pk)


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_data)
    ]

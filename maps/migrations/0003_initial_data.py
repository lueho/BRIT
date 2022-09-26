# Generated by Django 3.2.10 on 2022-04-04 12:44

import re

from django.db import migrations


def create_initial_data(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model('auth', 'Permission')

    models = ['Attribute', 'RegionAttributeValue',]
    permission_prefixes = ['add', 'view', 'change', 'delete']

    editors, _ = Group.objects.get_or_create(name='editors')
    for model in models:
        model_class = apps.get_model('maps', model)
        content_type = ContentType.objects.get_for_model(model_class, for_concrete_model=False)
        verbose_name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", str(model_class.__name__)).lower()

        for prefix in permission_prefixes:
            codename = f'{prefix}_{model_class._meta.model_name}'
            name = f'Can {prefix} {verbose_name}'
            permission, _ = Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={'name': name})
            editors.permissions.add(permission)


class Migration(migrations.Migration):

    dependencies = [
        ('maps', '0002_attribute_regionattributevalue'),
        ('users', '0001_initial_data'),
    ]

    operations = [
        migrations.RunPython(create_initial_data)
    ]

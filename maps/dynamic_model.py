from functools import lru_cache
from django.db import connection, models as dj_models
from django.core.exceptions import ImproperlyConfigured


def get_dynamic_model(dataset):
    """
    Given a GeoDataset instance, return a Django model class that wraps the referenced table.
    This is read-only and only exposes the fields listed in GeoDataset.display_fields, filter_fields, and geometry_field.
    """
    table_name = dataset.table_name
    geometry_field = dataset.geometry_field
    display_fields = [f.strip() for f in (dataset.display_fields or '').split(',') if f.strip()]
    filter_fields = [f.strip() for f in (dataset.filter_fields or '').split(',') if f.strip()]
    all_fields = set(display_fields + filter_fields + [geometry_field])

    # Introspect the table
    with connection.cursor() as cursor:
        try:
            desc = connection.introspection.get_table_description(cursor, table_name)
        except Exception as e:
            raise ImproperlyConfigured(f"Table '{table_name}' not found: {e}")

    # Build fields dict
    fields = {
        '__module__': __name__,
        'Meta': type('Meta', (), {'managed': False, 'db_table': table_name, 'app_label': 'maps'})
    }
    for col in desc:
        if col.name in all_fields:
            # Use CharField for simplicity; for geometry, use GeometryField if needed
            if col.name == geometry_field:
                # Use a placeholder for geometry field (should be improved if needed)
                fields[col.name] = dj_models.TextField()
            else:
                fields[col.name] = dj_models.TextField()
    # Always add a primary key
    fields['id'] = dj_models.AutoField(primary_key=True)
    model_name = f'DynModel_{dataset.pk}_{table_name}'
    return type(model_name, (dj_models.Model,), fields)


@lru_cache(maxsize=256)
def get_dynamic_model_cached(dataset_pk):
    from maps.models import GeoDataset
    ds = GeoDataset.objects.get(pk=dataset_pk)
    return get_dynamic_model(ds)

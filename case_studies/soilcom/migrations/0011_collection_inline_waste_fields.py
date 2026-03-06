import django.db.models.deletion
from django.db import migrations, models


def _fk_attname(through_model, related_model_name):
    for field in through_model._meta.fields:
        if (
            field.is_relation
            and field.related_model is not None
            and field.related_model._meta.model_name == related_model_name
        ):
            return field.attname
    raise LookupError(
        f"Could not find foreign key to '{related_model_name}' on {through_model.__name__}"
    )


def backfill_inline_waste_fields(apps, schema_editor):
    Collection = apps.get_model("soilcom", "Collection")
    WasteStream = apps.get_model("soilcom", "WasteStream")

    CollectionAllowed = Collection.allowed_materials.through
    CollectionForbidden = Collection.forbidden_materials.through
    WasteStreamAllowed = WasteStream.allowed_materials.through
    WasteStreamForbidden = WasteStream.forbidden_materials.through

    collection_rows = list(
        Collection.objects.filter(waste_stream_id__isnull=False).values(
            "id", "waste_stream_id", "waste_category_id"
        )
    )
    if not collection_rows:
        return

    waste_stream_ids = {row["waste_stream_id"] for row in collection_rows}

    ws_to_category = dict(
        WasteStream.objects.filter(id__in=waste_stream_ids).values_list(
            "id", "category_id"
        )
    )

    category_updates = []
    for row in collection_rows:
        if row["waste_category_id"] is not None:
            continue
        category_id = ws_to_category.get(row["waste_stream_id"])
        if category_id is None:
            continue
        category_updates.append(Collection(id=row["id"], waste_category_id=category_id))

    if category_updates:
        Collection.objects.bulk_update(category_updates, ["waste_category"], batch_size=1000)

    ws_allowed_ws_fk = _fk_attname(WasteStreamAllowed, "wastestream")
    ws_allowed_mat_fk = _fk_attname(WasteStreamAllowed, "material")
    ws_forbidden_ws_fk = _fk_attname(WasteStreamForbidden, "wastestream")
    ws_forbidden_mat_fk = _fk_attname(WasteStreamForbidden, "material")

    col_allowed_col_fk = _fk_attname(CollectionAllowed, "collection")
    col_allowed_mat_fk = _fk_attname(CollectionAllowed, "material")
    col_forbidden_col_fk = _fk_attname(CollectionForbidden, "collection")
    col_forbidden_mat_fk = _fk_attname(CollectionForbidden, "material")

    allowed_by_stream = {}
    for ws_id, mat_id in WasteStreamAllowed.objects.filter(
        **{f"{ws_allowed_ws_fk}__in": waste_stream_ids}
    ).values_list(ws_allowed_ws_fk, ws_allowed_mat_fk):
        allowed_by_stream.setdefault(ws_id, set()).add(mat_id)

    forbidden_by_stream = {}
    for ws_id, mat_id in WasteStreamForbidden.objects.filter(
        **{f"{ws_forbidden_ws_fk}__in": waste_stream_ids}
    ).values_list(ws_forbidden_ws_fk, ws_forbidden_mat_fk):
        forbidden_by_stream.setdefault(ws_id, set()).add(mat_id)

    existing_allowed = set(
        CollectionAllowed.objects.values_list(col_allowed_col_fk, col_allowed_mat_fk)
    )
    existing_forbidden = set(
        CollectionForbidden.objects.values_list(col_forbidden_col_fk, col_forbidden_mat_fk)
    )

    new_allowed = []
    new_forbidden = []

    for row in collection_rows:
        collection_id = row["id"]
        waste_stream_id = row["waste_stream_id"]

        for material_id in allowed_by_stream.get(waste_stream_id, set()):
            pair = (collection_id, material_id)
            if pair in existing_allowed:
                continue
            existing_allowed.add(pair)
            new_allowed.append(
                CollectionAllowed(
                    **{
                        col_allowed_col_fk: collection_id,
                        col_allowed_mat_fk: material_id,
                    }
                )
            )

        for material_id in forbidden_by_stream.get(waste_stream_id, set()):
            pair = (collection_id, material_id)
            if pair in existing_forbidden:
                continue
            existing_forbidden.add(pair)
            new_forbidden.append(
                CollectionForbidden(
                    **{
                        col_forbidden_col_fk: collection_id,
                        col_forbidden_mat_fk: material_id,
                    }
                )
            )

    if new_allowed:
        CollectionAllowed.objects.bulk_create(
            new_allowed, batch_size=1000, ignore_conflicts=True
        )
    if new_forbidden:
        CollectionForbidden.objects.bulk_create(
            new_forbidden, batch_size=1000, ignore_conflicts=True
        )


class Migration(migrations.Migration):
    dependencies = [
        ("soilcom", "0010_add_sorting_method_and_established"),
    ]

    operations = [
        migrations.AddField(
            model_name="collection",
            name="waste_category",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="collections",
                to="soilcom.wastecategory",
            ),
        ),
        migrations.AddField(
            model_name="collection",
            name="allowed_materials",
            field=models.ManyToManyField(
                blank=True,
                related_name="allowed_in_collections",
                to="materials.material",
            ),
        ),
        migrations.AddField(
            model_name="collection",
            name="forbidden_materials",
            field=models.ManyToManyField(
                blank=True,
                related_name="forbidden_in_collections",
                to="materials.material",
            ),
        ),
        migrations.RunPython(backfill_inline_waste_fields, migrations.RunPython.noop),
    ]

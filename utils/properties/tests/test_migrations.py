from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class RemoveLegacyUnitFieldMigrationTestCase(TransactionTestCase):
    """The legacy ``unit`` char field must be resolved into ``allowed_units``
    before it is dropped, for both ``Property`` and ``MaterialProperty``."""

    migrate_from = [
        ("properties", "0009_collection_point_property"),
        ("materials", "0027_materialcomponentgroup_is_compositional"),
    ]
    migrate_to = [
        ("properties", "0010_remove_property_unit"),
        ("materials", "0028_remove_materialproperty_unit"),
    ]

    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.executor.migrate(self.migrate_from)
        self.old_apps = self.executor.loader.project_state(self.migrate_from).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def _migrate_forward(self):
        self.executor.loader.build_graph()
        self.executor.migrate(self.migrate_to)
        return self.executor.loader.project_state(self.migrate_to).apps

    def _create_owner(self, apps, username):
        return apps.get_model("auth", "User").objects.create(username=username)

    def test_property_legacy_label_is_resolved_into_existing_unit(self):
        Unit = self.old_apps.get_model("properties", "Unit")
        Property = self.old_apps.get_model("properties", "Property")
        owner = self._create_owner(self.old_apps, "legacy-owner")
        unit = Unit.objects.create(owner=owner, name="kilogram", symbol="kg")
        prop = Property.objects.create(owner=owner, name="Mass", unit="kg")

        new_apps = self._migrate_forward()

        migrated = new_apps.get_model("properties", "Property").objects.get(pk=prop.pk)
        self.assertEqual(
            list(migrated.allowed_units.values_list("pk", flat=True)), [unit.pk]
        )

    def test_material_property_unresolvable_label_creates_unit(self):
        MaterialProperty = self.old_apps.get_model("materials", "MaterialProperty")
        owner = self._create_owner(self.old_apps, "legacy-owner")
        prop = MaterialProperty.objects.create(
            owner=owner, name="Phosphorus", unit="kg/m³"
        )

        new_apps = self._migrate_forward()

        migrated = new_apps.get_model("materials", "MaterialProperty").objects.get(
            pk=prop.pk
        )
        units = list(migrated.allowed_units.all())
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].name, "kg/m³")
        self.assertEqual(units[0].symbol, "kg/m³")
        self.assertEqual(units[0].owner_id, owner.pk)

    def test_existing_allowed_units_are_left_untouched(self):
        Unit = self.old_apps.get_model("properties", "Unit")
        Property = self.old_apps.get_model("properties", "Property")
        owner = self._create_owner(self.old_apps, "legacy-owner")
        structured = Unit.objects.create(owner=owner, name="tonne", symbol="t")
        prop = Property.objects.create(owner=owner, name="Mass", unit="kg")
        prop.allowed_units.add(structured)

        new_apps = self._migrate_forward()

        migrated = new_apps.get_model("properties", "Property").objects.get(pk=prop.pk)
        self.assertEqual(
            list(migrated.allowed_units.values_list("pk", flat=True)),
            [structured.pk],
        )

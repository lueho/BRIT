import importlib
import sys

from django.contrib import admin
from django.test import SimpleTestCase

from bibliography.admin import LicenceAdmin
from case_studies.closecycle.admin import ShowcaseAdmin
from distributions.admin import TemporalDistributionAdmin, TimestepAdmin
from interfaces.simucf.admin import InputMaterialAdmin
from inventories.admin import ScenarioAdmin, ScenarioInventoryConfigurationAdmin
from materials.admin import (
    MaterialAdmin,
    MaterialComponentAdmin,
    MaterialComponentGroupAdmin,
    MaterialPropertyAdmin,
    MaterialPropertyGroupAdmin,
    SampleAdmin,
    SampleGroupAdmin,
    SampleSeriesAdmin,
)
from processes.admin import (
    ProcessAdmin,
    ProcessCategoryAdmin,
    ProcessMaterialAdmin,
    ProcessMaterialInline,
    ProcessOperatingParameterAdmin,
    ProcessOperatingParameterInline,
)
from sources.greenhouses.admin import CultureAdmin, GreenhouseAdmin
from sources.waste_collection.admin import (
    BinConfigurationAdmin,
    CollectionAdmin,
    CollectionFrequencyAdmin,
    CollectionSystemAdmin,
    CollectorAdmin,
    FeeSystemAdmin,
    WasteCategoryAdmin,
    WasteComponentAdmin,
)
from utils.object_management.admin import NamedUserCreatedObjectAdmin
from utils.properties.admin import PropertyAdmin, UnitAdmin

BASE_LIST_DISPLAY = ("name", "owner", "publication_status")
BASE_SEARCH_FIELDS = ("name",)
BASE_LIST_FILTER = ("publication_status",)
BASE_ORDERING = ("name",)


def first_party_model_admins():
    """Yield project ModelAdmin instances from the default admin site registry."""
    for model_admin in admin.site._registry.values():
        top_level = type(model_admin).__module__.split(".")[0]
        module = sys.modules.get(top_level) or importlib.import_module(top_level)
        if module.__file__ and "site-packages" in module.__file__:
            continue
        yield model_admin


class NamedUserCreatedObjectAdminTest(SimpleTestCase):
    def test_shared_defaults(self):
        self.assertEqual(BASE_LIST_DISPLAY, NamedUserCreatedObjectAdmin.list_display)
        self.assertEqual(BASE_SEARCH_FIELDS, NamedUserCreatedObjectAdmin.search_fields)
        self.assertEqual(BASE_LIST_FILTER, NamedUserCreatedObjectAdmin.list_filter)
        self.assertEqual(BASE_ORDERING, NamedUserCreatedObjectAdmin.ordering)

    def test_plain_named_model_admins_use_shared_base(self):
        admin_classes = (
            BinConfigurationAdmin,
            CollectionSystemAdmin,
            FeeSystemAdmin,
            MaterialComponentGroupAdmin,
            MaterialPropertyGroupAdmin,
            ProcessCategoryAdmin,
            TemporalDistributionAdmin,
            WasteCategoryAdmin,
            WasteComponentAdmin,
        )
        for admin_class in admin_classes:
            with self.subTest(admin_class=admin_class.__name__):
                self.assertTrue(issubclass(admin_class, NamedUserCreatedObjectAdmin))
                self.assertEqual(BASE_LIST_DISPLAY, admin_class.list_display)
                self.assertEqual(BASE_SEARCH_FIELDS, admin_class.search_fields)
                self.assertEqual(BASE_LIST_FILTER, admin_class.list_filter)
                self.assertEqual(BASE_ORDERING, admin_class.ordering)

    def test_named_model_admins_with_overrides_use_shared_base(self):
        admin_classes = (
            CollectionAdmin,
            CollectionFrequencyAdmin,
            CollectorAdmin,
            CultureAdmin,
            GreenhouseAdmin,
            InputMaterialAdmin,
            LicenceAdmin,
            MaterialAdmin,
            MaterialComponentAdmin,
            MaterialPropertyAdmin,
            ProcessAdmin,
            PropertyAdmin,
            SampleAdmin,
            SampleGroupAdmin,
            SampleSeriesAdmin,
            ScenarioAdmin,
            ShowcaseAdmin,
            TimestepAdmin,
            UnitAdmin,
        )
        for admin_class in admin_classes:
            with self.subTest(admin_class=admin_class.__name__):
                self.assertTrue(issubclass(admin_class, NamedUserCreatedObjectAdmin))

    def test_overrides_are_preserved(self):
        self.assertEqual(
            ("name", "website", "catchment", "owner", "publication_status"),
            CollectorAdmin.list_display,
        )
        self.assertEqual(("name", "description"), CollectorAdmin.search_fields)
        self.assertEqual(
            ("name", "abbreviation", "description"), MaterialAdmin.search_fields
        )
        self.assertEqual(
            ("publication_status", "type"), CollectionFrequencyAdmin.list_filter
        )
        self.assertEqual(("distribution", "order"), TimestepAdmin.ordering)


class AutocompleteFieldsTest(SimpleTestCase):
    def test_fk_admin_autocomplete_fields(self):
        self.assertEqual(
            ("process", "material", "quantity_unit"),
            ProcessMaterialAdmin.autocomplete_fields,
        )
        self.assertEqual(
            ("process", "unit"), ProcessOperatingParameterAdmin.autocomplete_fields
        )
        self.assertEqual(
            (
                "scenario",
                "feedstock",
                "sample_series",
                "geodataset",
                "inventory_algorithm",
                "inventory_parameter",
                "inventory_value",
            ),
            ScenarioInventoryConfigurationAdmin.autocomplete_fields,
        )

    def test_inline_autocomplete_fields(self):
        self.assertEqual(
            ("material", "quantity_unit"), ProcessMaterialInline.autocomplete_fields
        )
        self.assertEqual(("unit",), ProcessOperatingParameterInline.autocomplete_fields)

    def test_autocomplete_targets_are_searchable(self):
        for model_admin in first_party_model_admins():
            for field_name in model_admin.get_autocomplete_fields(None):
                field = model_admin.model._meta.get_field(field_name)
                target_admin = admin.site._registry.get(field.remote_field.model)
                with self.subTest(admin=type(model_admin).__name__, field=field_name):
                    self.assertIsNotNone(
                        target_admin,
                        f"{field.remote_field.model} is not registered in admin",
                    )
                    self.assertTrue(
                        target_admin.search_fields,
                        f"{type(target_admin).__name__} must define search_fields "
                        f"for autocomplete_fields",
                    )


class AdminOptionSyntaxTest(SimpleTestCase):
    TUPLE_OPTION_ATTRS = (
        "actions",
        "autocomplete_fields",
        "filter_horizontal",
        "inlines",
        "list_display",
        "list_display_links",
        "list_editable",
        "list_filter",
        "ordering",
        "raw_id_fields",
        "readonly_fields",
        "search_fields",
    )

    def test_admin_options_use_tuple_syntax(self):
        for model_admin in first_party_model_admins():
            for attr in self.TUPLE_OPTION_ATTRS:
                value = getattr(model_admin, attr, None)
                if value is None:
                    continue
                with self.subTest(admin=type(model_admin).__name__, attr=attr):
                    self.assertIsInstance(value, tuple)

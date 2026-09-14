import contextlib
import logging

from django.contrib.gis.geos import GEOSGeometry
from django.db.models import QuerySet
from django.test import TestCase
from django.urls import reverse

from maps.models import GeoPolygon
from utils.properties.models import PropertyBase, Unit

from ..models import (
    Attribute,
    Catchment,
    CategoricalAttribute,
    GeoDataset,
    GeoDatasetColumnPolicy,
    GeoDatasetRuntimeConfiguration,
    LauRegion,
    NutsRegion,
    Region,
    RegionAttributeTextValue,
    RegionAttributeValue,
    RegionProperty,
)


@contextlib.contextmanager
def assert_no_warning(logger_name, msg_contains):
    """Assert that no warning containing msg_contains is logged."""
    logger = logging.getLogger(logger_name)
    handler = logging.StreamHandler()
    handler.setLevel(logging.WARNING)
    records = []
    handler.handle = lambda record: records.append(record)
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        for record in records:
            if msg_contains in record.getMessage():
                raise AssertionError(
                    f"Unexpected warning logged: {record.getMessage()}"
                )


class RegionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        country_wkt = "MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))"
        cls.country_borders = GeoPolygon.objects.create(
            geom=GEOSGeometry(country_wkt, srid=4326)
        )
        cls.country_region = NutsRegion.objects.create(
            name="Country", levl_code=0, cntr_code="DE", borders=cls.country_borders
        )

        # Create a catchment polygon that is almost entirely within the country.
        # Its coordinates are chosen so that without the buffer it might not be strictly contained,
        # but with the buffer (0.001°) the geometry becomes fully contained.
        catchment_wkt = (
            "MULTIPOLYGON((("
            "0 0, "  # bottom left
            "0 1, "  # top left
            "1 1, "  # top right (inside)
            "1.004 0.5, "  # tiny bump to the right (outside)
            "1 0, "  # bottom right (inside)
            "0 0"  # close the ring
            ")))"
        )
        cls.catchment_borders = GeoPolygon.objects.create(
            geom=GEOSGeometry(catchment_wkt, srid=4326)
        )

    def test_region_geom(self):
        self.assertEqual(self.country_borders.geom, self.country_region.geom)

    def test_country_field_automatically_set(self):
        catchment_region = Region.objects.create(
            name="Catchment Region", borders=self.catchment_borders
        )
        self.assertEqual(
            "DE",
            catchment_region.country,
        )


class CatchmentPostDeleteTestCase(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Test Region To Delete")
        self.fix_region = Region.objects.create(name="Test Region To Stay")
        self.catchment = Catchment.objects.create(
            name="Test Catchment", type="custom", region=self.region
        )
        self.catchment_2 = Catchment.objects.create(
            name="Test Catchment 2", type="administrative", region=self.fix_region
        )

    def test_after_deleting_catchment_unused_custom_region_is_also_deleted(self):
        self.catchment.delete()
        with self.assertRaises(Region.DoesNotExist):
            Region.objects.get(name="Test Region To Delete")

    def test_non_custom_regions_are_exempted_from_deletion(self):
        self.catchment_2.delete()
        Region.objects.get(name="Test Region To Stay")


class GeoDatasetModelTestCase(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Test Region")

    def test_get_map_url_uses_dataset_scoped_map_route(self):
        dataset = GeoDataset.objects.create(name="Dataset", region=self.region)

        self.assertEqual(
            dataset.get_map_url(),
            reverse("geodataset-map", kwargs={"pk": dataset.pk}),
        )

    def test_get_features_api_basename_prefers_explicit_field(self):
        dataset = GeoDataset.objects.create(
            name="Dataset",
            region=self.region,
            model_name="NutsRegion",
        )
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=dataset,
            features_api_basename="api-custom-dataset",
        )

        self.assertEqual(dataset.get_features_api_basename(), "api-custom-dataset")

    def test_get_features_api_basename_falls_back_to_runtime_model_name(self):
        dataset = GeoDataset.objects.create(name="Dataset", region=self.region)
        GeoDatasetRuntimeConfiguration.objects.create(
            dataset=dataset,
            backend_type="django_model",
            runtime_model_name="NutsRegion",
        )

        self.assertEqual(dataset.get_features_api_basename(), "api-nuts-region")

    def test_column_policy_helpers_return_allowlisted_columns(self):
        dataset = GeoDataset.objects.create(name="Dataset", region=self.region)
        GeoDatasetColumnPolicy.objects.create(
            dataset=dataset,
            column_name="name",
            is_visible=True,
            is_searchable=True,
        )
        GeoDatasetColumnPolicy.objects.create(
            dataset=dataset,
            column_name="category",
            is_visible=True,
            is_filterable=True,
            is_exportable=True,
        )

        self.assertEqual(dataset.get_visible_columns(), ["category", "name"])
        self.assertEqual(dataset.get_filterable_columns(), ["category"])
        self.assertEqual(dataset.get_searchable_columns(), ["name"])
        self.assertEqual(dataset.get_exportable_columns(), ["category"])


class CatchmentPedigreeTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        region = Region.objects.create(name="Test Region")
        cls.catchment = Catchment.objects.create(name="Test Catchment", region=region)
        cls.child_catchment_1 = Catchment.objects.create(
            name="Child 1", parent=cls.catchment
        )
        cls.child_catchment_2 = Catchment.objects.create(
            name="Child 2", parent=cls.catchment
        )
        cls.grandchild_catchment_1_1 = Catchment.objects.create(
            name="Grandchild 1 1", parent=cls.child_catchment_1
        )
        cls.grandchild_catchment_1_2 = Catchment.objects.create(
            name="Grandchild 1 2", parent=cls.child_catchment_1
        )
        cls.grandchild_catchment_2_1 = Catchment.objects.create(
            name="Grandchild 2 1", parent=cls.child_catchment_2
        )
        cls.great_grandchild_catchment_1_1_1 = Catchment.objects.create(
            name="Great Grandchild 1 1 1", parent=cls.grandchild_catchment_1_1
        )
        cls.great_grandchild_catchment_2_1_1 = Catchment.objects.create(
            name="Great Grandchild 2 1 1", parent=cls.grandchild_catchment_2_1
        )
        cls.unrelated_catchment = Catchment.objects.create(
            name="Unrelated Catchment", region=region
        )

    def test_downstream_pedigree_returns_catchment_queryset(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertIsInstance(pedigree, QuerySet)
        self.assertEqual(pedigree.model, Catchment)

    def test_downstream_pedigree_includes_self(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertIn(self.catchment, pedigree)

    def test_downstream_pedigree_includes_children(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertIn(self.child_catchment_1, pedigree)
        self.assertIn(self.child_catchment_2, pedigree)

    def test_downstream_pedigree_includes_grandchildren_of_all_children(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertIn(self.grandchild_catchment_1_1, pedigree)
        self.assertIn(self.grandchild_catchment_1_2, pedigree)
        self.assertIn(self.grandchild_catchment_2_1, pedigree)

    def test_downstream_pedigree_includes_great_grandchildren_of_all_grandchildren(
        self,
    ):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertIn(self.great_grandchild_catchment_1_1_1, pedigree)
        self.assertIn(self.great_grandchild_catchment_2_1_1, pedigree)

    def test_downstream_pedigree_excludes_unrelated_catchment(self):
        pedigree = self.catchment.descendants(include_self=True)
        self.assertNotIn(self.unrelated_catchment, pedigree)


class RegionAttributeValueMeasurementTestCase(TestCase):
    def test_shared_numeric_measurement_properties_are_available(self):
        region = Region.objects.create(name="Test Region")
        region_property = RegionProperty.objects.create(
            name="Population density",
            unit="1/km²",
        )
        value = RegionAttributeValue.objects.create(
            region=region,
            property=region_property,
            value=123.321,
            standard_deviation=1.25,
        )

        self.assertEqual(value.measurement_name, region_property.name)
        self.assertEqual(value.measurement_unit_label, region_property.unit)
        self.assertEqual(value.display_average, value.value)
        self.assertEqual(value.display_standard_deviation, value.standard_deviation)

    def test_save_assigns_matching_unit_from_property(self):
        region = Region.objects.create(name="Test Region")
        region_property = RegionProperty.objects.create(
            name="Population density",
            unit="1/km²",
        )
        unit = Unit.objects.create(
            name="People per square kilometre",
            symbol="1/km²",
        )

        value = RegionAttributeValue.objects.create(
            region=region,
            property=region_property,
            value=123.321,
        )

        self.assertEqual(value.unit, unit)
        self.assertEqual(value.measurement_unit_label, unit.name)

    def test_save_leaves_unit_empty_when_property_unit_cannot_be_resolved(self):
        value = RegionAttributeValue.objects.create(
            region=Region.objects.create(name="Test Region"),
            property=RegionProperty.objects.create(name="Area", unit="km²"),
            value=123.321,
        )

        self.assertIsNone(value.unit)

    def test_value_level_unit_takes_precedence_over_property_unit(self):
        region = Region.objects.create(name="Test Region")
        region_property = RegionProperty.objects.create(
            name="Population density",
            unit="1/km²",
        )
        unit = Unit.objects.create(name="1/km²", symbol="1/km²")
        value = RegionAttributeValue.objects.create(
            region=region,
            property=region_property,
            unit=unit,
            value=123.321,
        )

        self.assertEqual(value.measurement_unit_label, unit.name)


class AttributePropertyBaseContractTestCase(TestCase):
    def test_attribute_uses_shared_property_base_contract(self):
        attribute = Attribute.objects.create(name="Population density", unit="1/km²")

        self.assertIsInstance(attribute, PropertyBase)


class RegionPropertyBaseContractTestCase(TestCase):
    def test_region_property_uses_shared_property_base_contract(self):
        region_property = RegionProperty.objects.create(
            name="Population density",
            unit="1/km²",
        )

        self.assertIsInstance(region_property, PropertyBase)


class RegionAttributeTextValueCategoricalAttributeTestCase(TestCase):
    def test_text_values_use_separate_categorical_attribute_definition(self):
        region = Region.objects.create(name="Test Region")
        categorical_attribute = CategoricalAttribute.objects.create(
            name="Urban rural remoteness"
        )
        value = RegionAttributeTextValue.objects.create(
            region=region,
            categorical_attribute=categorical_attribute,
            value="intermediate, close to a city",
        )

        self.assertEqual(value.categorical_attribute.name, "Urban rural remoteness")


class LauCatchmentParentSignalTestCase(TestCase):
    """Regression test: LAU catchments must get the correct tree parent on creation.

    When a LAU catchment is created its ``parent_id`` must point to the
    *Catchment* wrapping the NUTS parent region, not to the NutsRegion row PK
    (which lives in a separate ID space and may coincide with an unrelated
    Catchment PK).
    """

    @classmethod
    def setUpTestData(cls):
        nuts0 = NutsRegion.objects.create(
            nuts_id="ZZ", levl_code=0, name_latn="Test Country"
        )
        nuts1 = NutsRegion.objects.create(
            nuts_id="ZZ1", levl_code=1, name_latn="Test Region 1", parent=nuts0
        )
        nuts3 = NutsRegion.objects.create(
            nuts_id="ZZ123", levl_code=3, name_latn="Test Region 3", parent=nuts1
        )
        cls.nuts3_catchment = Catchment.objects.create(
            name="NUTS3 Catchment", region=nuts3.region_ptr, type="nuts"
        )
        lau = LauRegion.objects.create(
            lau_id="ZZ00001", lau_name="Test Municipality", nuts_parent=nuts3
        )
        cls.lau_catchment = Catchment.objects.create(region=lau.region_ptr, type="lau")

    def test_lau_catchment_parent_is_nuts3_catchment(self):
        self.lau_catchment.refresh_from_db()
        self.assertEqual(self.lau_catchment.parent_id, self.nuts3_catchment.pk)

    def test_lau_catchment_is_descendant_of_nuts3_catchment(self):
        self.lau_catchment.refresh_from_db()
        descendants = list(self.nuts3_catchment.descendants(include_self=True))
        self.assertIn(self.lau_catchment, descendants)


class CustomCatchmentParentMismatchSignalTestCase(TestCase):
    """A warning is logged when a custom catchment has negligible spatial
    overlap (< 1% of the smaller geometry's area) with its tree parent.

    Custom catchments (e.g. waste-management associations) may legitimately
    partially overlap their parent, but a sliver-level overlap means the
    parent assignment is wrong.  The signal warns non-blocking so the save
    still succeeds.
    """

    @classmethod
    def setUpTestData(cls):
        cls.parent_region = Region.objects.create(
            name="Parent Region",
            country="DE",
            type="nuts",
            borders=GeoPolygon.objects.create(
                geom=GEOSGeometry(
                    "MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))", srid=4326
                )
            ),
        )
        cls.parent_catchment = Catchment.objects.create(
            name="Parent NUTS",
            type="nuts",
            region=cls.parent_region,
        )

    def test_warning_logged_when_custom_catchment_has_negligible_overlap(self):
        outside_region = Region.objects.create(
            name="Outside Region",
            country="DE",
            type="custom",
            borders=GeoPolygon.objects.create(
                geom=GEOSGeometry(
                    "MULTIPOLYGON(((2 2, 2 3, 3 3, 3 2, 2 2)))", srid=4326
                )
            ),
        )
        with self.assertLogs("maps.signals", level="WARNING") as cm:
            Catchment.objects.create(
                name="Outside Custom",
                type="custom",
                parent=self.parent_catchment,
                region=outside_region,
            )
        self.assertIn("spatial overlap with", "\n".join(cm.output))

    def test_no_warning_when_custom_catchment_substantially_overlaps_parent(self):
        inside_region = Region.objects.create(
            name="Inside Region",
            country="DE",
            type="custom",
            borders=GeoPolygon.objects.create(
                geom=GEOSGeometry(
                    "MULTIPOLYGON(((0.1 0.1, 0.1 0.9, 0.9 0.9, 0.9 0.1, 0.1 0.1)))",
                    srid=4326,
                )
            ),
        )
        with assert_no_warning("maps.signals", "spatial overlap with"):
            Catchment.objects.create(
                name="Inside Custom",
                type="custom",
                parent=self.parent_catchment,
                region=inside_region,
            )

    def test_no_warning_for_non_custom_catchment(self):
        admin_region = Region.objects.create(
            name="Admin Region",
            country="DE",
            type="administrative",
            borders=GeoPolygon.objects.create(
                geom=GEOSGeometry(
                    "MULTIPOLYGON(((2 2, 2 3, 3 3, 3 2, 2 2)))", srid=4326
                )
            ),
        )
        with assert_no_warning("maps.signals", "spatial overlap with"):
            Catchment.objects.create(
                name="Admin Child",
                type="administrative",
                parent=self.parent_catchment,
                region=admin_region,
            )


class NutsRegionTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        nuts0 = NutsRegion.objects.create(
            nuts_id="UK", levl_code=0, name_latn="United Kingdom"
        )
        nuts1 = NutsRegion.objects.create(
            nuts_id="UKH", levl_code=1, name_latn="East of England", parent=nuts0
        )
        nuts2 = NutsRegion.objects.create(
            nuts_id="UKH1", levl_code=2, name_latn="East Anglia", parent=nuts1
        )
        NutsRegion.objects.create(
            nuts_id="UKH2",
            levl_code=2,
            name_latn="Bedfordshire and Hertfordshire",
            parent=nuts1,
        )
        NutsRegion.objects.create(
            nuts_id="UKH11", levl_code=3, name_latn="Peterborough", parent=nuts2
        )
        nuts3 = NutsRegion.objects.create(
            nuts_id="UKH14", levl_code=3, name_latn="Suffolk", parent=nuts2
        )
        LauRegion.objects.create(
            lau_id="E07000200", lau_name="Babergh", nuts_parent=nuts3
        )
        LauRegion.objects.create(
            lau_id="E07000202", lau_name="Ipswich", nuts_parent=nuts3
        )

    def setUp(self):
        pass

    def test_pedigree_starting_from_lvl_0(self):
        region = NutsRegion.objects.get(levl_code=0)
        expected = {
            "qs_0": NutsRegion.objects.filter(levl_code=0),
            "qs_1": NutsRegion.objects.filter(levl_code=1),
            "qs_2": NutsRegion.objects.filter(levl_code=2),
            "qs_3": NutsRegion.objects.filter(levl_code=3),
        }
        pedigree = region.pedigree
        self.assertEqual(set(pedigree.keys()), set(expected.keys()))
        for key, value in pedigree.items():
            self.assertIsInstance(value, QuerySet)
            self.assertEqual(set(pedigree[key]), set(expected[key]))

    def test_pedigree_starting_from_lvl_1(self):
        region = NutsRegion.objects.get(levl_code=1)
        expected = {
            "qs_0": NutsRegion.objects.filter(levl_code=0),
            "qs_1": NutsRegion.objects.filter(levl_code=1),
            "qs_2": NutsRegion.objects.filter(levl_code=2),
            "qs_3": NutsRegion.objects.filter(levl_code=3),
        }
        pedigree = region.pedigree
        self.assertEqual(set(pedigree.keys()), set(expected.keys()))
        for key, value in pedigree.items():
            self.assertIsInstance(value, QuerySet)
            self.assertEqual(set(pedigree[key]), set(expected[key]))

    def test_pedigree_starting_from_lvl_2(self):
        region = NutsRegion.objects.get(nuts_id="UKH1")
        expected = {
            "qs_0": NutsRegion.objects.filter(nuts_id="UK"),
            "qs_1": NutsRegion.objects.filter(nuts_id="UKH"),
            "qs_2": NutsRegion.objects.filter(nuts_id="UKH1"),
            "qs_3": NutsRegion.objects.filter(levl_code=3),
        }
        pedigree = region.pedigree
        self.assertEqual(set(pedigree.keys()), set(expected.keys()))
        for key, value in pedigree.items():
            self.assertIsInstance(value, QuerySet)
            self.assertEqual(set(pedigree[key]), set(expected[key]))

    def test_pedigree_starting_from_lvl_3(self):
        region = NutsRegion.objects.get(nuts_id="UKH14")
        expected = {
            "qs_0": NutsRegion.objects.filter(nuts_id="UK"),
            "qs_1": NutsRegion.objects.filter(nuts_id="UKH"),
            "qs_2": NutsRegion.objects.filter(nuts_id="UKH1"),
            "qs_3": NutsRegion.objects.filter(nuts_id="UKH14"),
            "qs_4": LauRegion.objects.all(),
        }
        pedigree = region.pedigree
        self.assertEqual(set(pedigree.keys()), set(expected.keys()))
        for key, value in pedigree.items():
            self.assertIsInstance(value, QuerySet)
            self.assertEqual(set(pedigree[key]), set(expected[key]))

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from inventories.models import InventoryAlgorithm, Scenario, ScenarioStatus
from layer_manager.models import Layer, LayerAggregatedValue
from maps.models import Catchment, GeoDataset, GeoPolygon, Region
from materials.models import Material
from processes.models import Process
from utils.tests.testcases import AbstractTestCases

from ..models import Showcase


class ShowCaseCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    dashboard_view = False
    add_scope_query_param_to_list_urls = True

    model = Showcase

    view_create_name = "showcase-create"
    view_published_list_name = "showcase-list"
    view_private_list_name = "showcase-list-owned"
    view_detail_name = "showcase-detail"
    view_update_name = "showcase-update"
    view_delete_name = "showcase-delete-modal"

    create_object_data = {"name": "Test Showcase"}
    update_object_data = {"name": "Updated Test Showcase"}

    @classmethod
    def create_related_objects(cls):
        return {
            "region": Region.objects.create(
                name="Test Region", publication_status="published"
            )
        }

    def related_objects_post_data(self):
        """Include management form data for the inline formsets."""
        data = super().related_objects_post_data()
        data.update(
            {
                "showcase_materials-TOTAL_FORMS": "0",
                "showcase_materials-INITIAL_FORMS": "0",
                "showcase_materials-MIN_NUM_FORMS": "0",
                "showcase_materials-MAX_NUM_FORMS": "1000",
                "showcase_processes-TOTAL_FORMS": "0",
                "showcase_processes-INITIAL_FORMS": "0",
                "showcase_processes-MIN_NUM_FORMS": "0",
                "showcase_processes-MAX_NUM_FORMS": "1000",
            }
        )
        return data

    def test_create_view_renders_distinct_formset_controls_per_inline(self):
        """Each inline gets its own add button, container and empty-row template."""
        self.client.force_login(self.user_with_add_perm)
        response = self.client.get(self.get_create_url())
        self.assertEqual(response.status_code, 200)
        for prefix in ("showcase_materials", "showcase_processes"):
            for element in ("add-form", "formset-container", "empty-form-row"):
                with self.subTest(prefix=prefix, element=element):
                    self.assertContains(
                        response, f'id="{prefix}_{element}"', count=1, html=False
                    )
            self.assertContains(response, f'data-formset-id="{prefix}"', count=1)

    def test_create_and_update_forms_load_leaflet_for_the_location_widget(self):
        """The geometry widget needs Leaflet and leaflet-draw on the page."""
        pages = (
            (self.user_with_add_perm, self.get_create_url()),
            (self.owner_user, self.get_update_url(self.unpublished_object.pk)),
        )
        for user, url in pages:
            with self.subTest(url=url):
                self.client.force_login(user)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "leaflet/leaflet.js")
                self.assertContains(response, "leaflet-draw/leaflet.draw.min.js")
                self.assertContains(response, "leaflet/leaflet.forms.js")

    def test_create_view_post_with_inline_materials_and_processes(self):
        """Creating a showcase can attach material and process links inline."""
        self.client.force_login(self.user_with_add_perm)
        material = Material.objects.create(
            name="Inline Feedstock", publication_status="published"
        )
        process = Process.objects.create(
            name="Inline Process", publication_status="published"
        )
        data = {
            "name": "Chained Showcase",
            "region": self.related_objects["region"].pk,
            "showcase_materials-TOTAL_FORMS": "1",
            "showcase_materials-INITIAL_FORMS": "0",
            "showcase_materials-MIN_NUM_FORMS": "0",
            "showcase_materials-MAX_NUM_FORMS": "1000",
            "showcase_materials-0-material": str(material.pk),
            "showcase_materials-0-role": "input",
            "showcase_materials-0-order": "0",
            "showcase_processes-TOTAL_FORMS": "1",
            "showcase_processes-INITIAL_FORMS": "0",
            "showcase_processes-MIN_NUM_FORMS": "0",
            "showcase_processes-MAX_NUM_FORMS": "1000",
            "showcase_processes-0-process": str(process.pk),
            "showcase_processes-0-order": "0",
        }
        response = self.client.post(self.get_create_url(), data)
        self.assertEqual(response.status_code, 302)
        showcase = Showcase.objects.get(name="Chained Showcase")
        link = showcase.showcase_materials.get()
        self.assertEqual(material, link.material)
        self.assertEqual("input", link.role)
        self.assertEqual([process], showcase.process_chain)

    def test_update_view_post_replaces_inline_links(self):
        """Updating a showcase can reorder the process chain inline."""
        self.client.force_login(self.owner_user)
        process_a = Process.objects.create(
            name="First Process", publication_status="published"
        )
        process_b = Process.objects.create(
            name="Second Process", publication_status="published"
        )
        showcase = self.unpublished_object
        link = showcase.showcase_processes.create(process=process_a, order=1)
        data = {
            "name": "Updated Test Showcase",
            "region": self.related_objects["region"].pk,
            "showcase_materials-TOTAL_FORMS": "0",
            "showcase_materials-INITIAL_FORMS": "0",
            "showcase_materials-MIN_NUM_FORMS": "0",
            "showcase_materials-MAX_NUM_FORMS": "1000",
            "showcase_processes-TOTAL_FORMS": "2",
            "showcase_processes-INITIAL_FORMS": "1",
            "showcase_processes-MIN_NUM_FORMS": "0",
            "showcase_processes-MAX_NUM_FORMS": "1000",
            "showcase_processes-0-id": str(link.pk),
            "showcase_processes-0-process": str(process_a.pk),
            "showcase_processes-0-order": "2",
            "showcase_processes-1-process": str(process_b.pk),
            "showcase_processes-1-order": "1",
        }
        response = self.client.post(self.get_update_url(showcase.pk), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual([process_b, process_a], showcase.process_chain)

    def test_detail_view_hides_private_connections_from_anonymous_users(self):
        owner = self.owner_user
        showcase = self.published_object
        public_material = Material.objects.create(
            name="Public Detail Feedstock", publication_status="published"
        )
        private_material = Material.objects.create(
            name="Private Detail Feedstock", owner=owner
        )
        for material in (public_material, private_material):
            showcase.showcase_materials.create(material=material, role="input")
        showcase.showcase_processes.create(
            process=Process.objects.create(name="Private Detail Step", owner=owner),
            order=1,
        )

        response = self.client.get(self.get_detail_url(showcase.pk))

        self.assertContains(response, "Public Detail Feedstock")
        self.assertNotContains(response, "Private Detail Feedstock")
        self.assertNotContains(response, "Private Detail Step")

        self.client.force_login(owner)
        response = self.client.get(self.get_detail_url(showcase.pk))
        self.assertContains(response, "Private Detail Feedstock")
        self.assertContains(response, "Private Detail Step")

    def test_detail_view_draws_processing_chain_by_stage(self):
        showcase = self.published_object
        for name, role in (
            ("Chain Grass", "input"),
            ("Chain Juice", "intermediate"),
            ("Chain Protein", "product"),
        ):
            showcase.showcase_materials.create(
                material=Material.objects.create(
                    name=name, publication_status="published"
                ),
                role=role,
            )
        showcase.showcase_processes.create(
            process=Process.objects.create(
                name="Chain Pressing", publication_status="published"
            ),
            order=1,
        )

        response = self.client.get(self.get_detail_url(showcase.pk))

        stages = [
            (stage["key"], [item.name for item in stage["items"]])
            for stage in response.context["chain_stages"]
        ]
        self.assertEqual(
            [
                ("input", ["Chain Grass"]),
                ("process", ["Chain Pressing"]),
                ("intermediate", ["Chain Juice"]),
                ("product", ["Chain Protein"]),
            ],
            stages,
        )
        self.assertContains(response, 'class="csd-flow"')

    def test_detail_view_omits_empty_chain_stages(self):
        showcase = self.published_object
        showcase.showcase_materials.create(
            material=Material.objects.create(
                name="Only Input", publication_status="published"
            ),
            role="input",
        )

        response = self.client.get(self.get_detail_url(showcase.pk))

        self.assertEqual(
            ["input"], [stage["key"] for stage in response.context["chain_stages"]]
        )

    def test_scenario_cards_show_headline_results_of_evaluated_scenarios(self):
        showcase = self.published_object
        feedstock = Material.objects.create(
            name="Card Feedstock", publication_status="published"
        )
        algorithm = InventoryAlgorithm.objects.create(
            name="Card Algorithm",
            geodataset=GeoDataset.objects.create(
                name="Card Dataset",
                region=showcase.region,
                publication_status="published",
            ),
        )
        evaluated = Scenario.objects.create(
            name="Evaluated Card Scenario",
            region=showcase.region,
            showcase=showcase,
            publication_status="published",
        )
        pending = Scenario.objects.create(
            name="Pending Card Scenario",
            region=showcase.region,
            showcase=showcase,
            publication_status="published",
        )
        for scenario in (evaluated, pending):
            layer = Layer.objects.create(
                name="Card layer",
                geom_type="MultiPolygon",
                table_name=f"result_card_{scenario.pk}",
                scenario=scenario,
                feedstock=feedstock,
                algorithm=algorithm,
            )
            LayerAggregatedValue.objects.create(
                layer=layer, name="Recovered protein", value=23.816, unit="Mg/a"
            )
        evaluated.set_status(ScenarioStatus.Status.FINISHED)

        response = self.client.get(self.get_detail_url(showcase.pk))

        cards = {
            card["scenario"].name: card for card in response.context["scenario_cards"]
        }
        self.assertTrue(cards["Evaluated Card Scenario"]["evaluated"])
        self.assertEqual(
            [("Recovered protein", 23.816, "Mg/a")],
            [
                (value.name, value.value, value.unit)
                for value in cards["Evaluated Card Scenario"]["results"]
            ],
        )
        self.assertFalse(cards["Pending Card Scenario"]["evaluated"])
        self.assertEqual([], cards["Pending Card Scenario"]["results"])
        self.assertContains(response, "23.8")
        self.assertContains(
            response, reverse("scenario-result", kwargs={"pk": evaluated.pk})
        )

    def test_scenario_cards_cap_headline_results(self):
        showcase = self.published_object
        feedstock = Material.objects.create(
            name="Cap Feedstock", publication_status="published"
        )
        algorithm = InventoryAlgorithm.objects.create(
            name="Cap Algorithm",
            geodataset=GeoDataset.objects.create(
                name="Cap Dataset",
                region=showcase.region,
                publication_status="published",
            ),
        )
        scenario = Scenario.objects.create(
            name="Many Results Scenario",
            region=showcase.region,
            showcase=showcase,
            publication_status="published",
        )
        layer = Layer.objects.create(
            name="Cap layer",
            geom_type="MultiPolygon",
            table_name=f"result_cap_{scenario.pk}",
            scenario=scenario,
            feedstock=feedstock,
            algorithm=algorithm,
        )
        for i in range(6):
            LayerAggregatedValue.objects.create(
                layer=layer, name=f"Value {i}", value=i, unit="Mg/a"
            )
        scenario.set_status(ScenarioStatus.Status.FINISHED)

        response = self.client.get(self.get_detail_url(showcase.pk))

        (card,) = response.context["scenario_cards"]
        self.assertEqual(
            ["Value 0", "Value 1", "Value 2", "Value 3"],
            [value.name for value in card["results"]],
        )
        self.assertEqual(2, card["more_results"])
        self.assertContains(response, "+2 more")

    def _card_layer(self, scenario, feedstock_name, prefix):
        return Layer.objects.create(
            name=f"{prefix} layer",
            geom_type="MultiPolygon",
            table_name=f"result_{prefix.lower()}_{scenario.pk}",
            scenario=scenario,
            feedstock=Material.objects.create(
                name=feedstock_name, publication_status="published"
            ),
            algorithm=InventoryAlgorithm.objects.create(
                name=f"{prefix} Algorithm",
                geodataset=GeoDataset.objects.create(
                    name=f"{prefix} Dataset",
                    region=scenario.region,
                    publication_status="published",
                ),
            ),
        )

    def test_scenario_cards_label_running_and_failed_scenarios(self):
        showcase = self.published_object
        expected = {
            "Changed Scenario": (ScenarioStatus.Status.CHANGED, "Not evaluated yet"),
            "Running Scenario": (ScenarioStatus.Status.RUNNING, "Evaluating"),
            "Failed Scenario": (ScenarioStatus.Status.FAILED, "Evaluation failed"),
        }
        for name, (status, _label) in expected.items():
            scenario = Scenario.objects.create(
                name=name,
                region=showcase.region,
                showcase=showcase,
                publication_status="published",
            )
            scenario.set_status(status)

        response = self.client.get(self.get_detail_url(showcase.pk))

        cards = {
            card["scenario"].name: card for card in response.context["scenario_cards"]
        }
        for name, (status, label) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(status, cards[name]["status"])
                self.assertFalse(cards[name]["evaluated"])
                self.assertContains(response, label)
        self.assertNotContains(response, "Show results")

    def test_scenario_cards_name_feedstock_when_scenario_has_several_layers(self):
        showcase = self.published_object
        scenario = Scenario.objects.create(
            name="Two Feedstock Scenario",
            region=showcase.region,
            showcase=showcase,
            publication_status="published",
        )
        for feedstock_name, prefix, value in (
            ("Clover grass", "Grass", 20),
            ("Wheat straw", "Straw", 35),
        ):
            LayerAggregatedValue.objects.create(
                layer=self._card_layer(scenario, feedstock_name, prefix),
                name="Total production",
                value=value,
                unit="Mg/a",
            )
        scenario.set_status(ScenarioStatus.Status.FINISHED)

        response = self.client.get(self.get_detail_url(showcase.pk))

        (card,) = response.context["scenario_cards"]
        self.assertTrue(card["several_layers"])
        self.assertContains(response, "Clover grass")
        self.assertContains(response, "Wheat straw")

    def test_scenario_cards_omit_feedstock_for_a_single_layer(self):
        showcase = self.published_object
        scenario = Scenario.objects.create(
            name="Single Feedstock Scenario",
            region=showcase.region,
            showcase=showcase,
            publication_status="published",
        )
        LayerAggregatedValue.objects.create(
            layer=self._card_layer(scenario, "Lonely feedstock", "Single"),
            name="Total production",
            value=5,
            unit="Mg/a",
        )
        scenario.set_status(ScenarioStatus.Status.FINISHED)

        response = self.client.get(self.get_detail_url(showcase.pk))

        (card,) = response.context["scenario_cards"]
        self.assertFalse(card["several_layers"])
        self.assertNotContains(response, 'class="csd-kpi-feedstock"')

    def test_detail_view_does_not_query_per_scenario(self):
        showcase = self.published_object
        for i in range(3):
            Scenario.objects.create(
                name=f"Query Scenario {i}",
                region=showcase.region,
                showcase=showcase,
                publication_status="published",
            )
        url = self.get_detail_url(showcase.pk)
        self.client.get(url)
        with CaptureQueriesContext(connection) as three:
            self.client.get(url)
        Scenario.objects.create(
            name="Query Scenario 3",
            region=showcase.region,
            showcase=showcase,
            publication_status="published",
        )
        with CaptureQueriesContext(connection) as four:
            self.client.get(url)

        self.assertEqual(len(three), len(four))

    def test_detail_map_omits_private_catchment_for_anonymous_users(self):
        owner = self.owner_user
        showcase = self.published_object
        showcase.catchment = Catchment.objects.create(
            name="Private Map Catchment", region=showcase.region, owner=owner
        )
        showcase.save()

        response = self.client.get(self.get_detail_url(showcase.pk))
        self.assertIsNone(response.context["view"].get_catchment_feature_id())

        self.client.force_login(owner)
        response = self.client.get(self.get_detail_url(showcase.pk))
        self.assertEqual(
            showcase.catchment.pk, response.context["view"].get_catchment_feature_id()
        )

    def test_detail_view_hides_private_region_from_anonymous_users(self):
        owner = self.owner_user
        showcase = self.published_object
        original_region = showcase.region
        showcase.region = Region.objects.create(
            name="Secret Pilot Region", country="SE", owner=owner
        )
        showcase.save()
        try:
            response = self.client.get(self.get_detail_url(showcase.pk))
            self.assertNotContains(response, "Secret Pilot Region")
            self.assertIsNone(response.context["view"].get_region_feature_id())

            self.client.force_login(owner)
            response = self.client.get(self.get_detail_url(showcase.pk))
            self.assertContains(response, "Secret Pilot Region")
            self.assertEqual(
                showcase.region_id, response.context["view"].get_region_feature_id()
            )
        finally:
            showcase.region = original_region
            showcase.save()

    def test_in_review_showcase_links_owner_to_review_view(self):
        showcase = Showcase.objects.create(
            name="SC99 - Pending showcase",
            owner=self.owner_user,
            region=self.published_object.region,
            publication_status="review",
        )
        review_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Showcase).pk,
                "object_id": showcase.pk,
            },
        )

        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_detail_url(showcase.pk))

        self.assertContains(response, review_url)
        self.assertContains(response, "Review view")

    def test_review_page_renders_showcase_detail_context(self):
        showcase = self.published_object
        showcase.showcase_materials.create(
            material=Material.objects.create(
                name="Review Input", publication_status="published"
            ),
            role="input",
        )
        review_url = reverse(
            "object_management:review_item_detail",
            kwargs={
                "content_type_id": ContentType.objects.get_for_model(Showcase).pk,
                "object_id": showcase.pk,
            },
        )

        self.client.force_login(self.owner_user)
        response = self.client.get(review_url)

        self.assertEqual(200, response.status_code)
        self.assertTrue(response.context["review_mode"])
        self.assertIn("map_config", response.context)
        self.assertIn("scenario_cards", response.context)
        self.assertEqual(
            ["input"], [stage["key"] for stage in response.context["chain_stages"]]
        )
        self.assertContains(response, "Review Input")


class ShowcaseGeoJSONVersionTestCase(TestCase):
    """The showcase GeoJSON serializes its region's name and borders, so the
    dataset version used for client cache revalidation must track them."""

    def setUp(self):
        self.region = Region.objects.create(
            name="Showcase Region", publication_status="published"
        )
        self.region.geom = MultiPolygon(Polygon.from_bbox((0, 0, 1, 1)))
        self.region.save()
        Showcase.objects.create(
            name="Showcase", region=self.region, publication_status="published"
        )

    def version(self):
        response = self.client.get(
            reverse("api-showcase-version"), {"scope": "published"}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["version"]

    def test_geojson_header_matches_version_action(self):
        response = self.client.get(
            reverse("api-showcase-geojson"), {"scope": "published"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Data-Version"], self.version())

    def test_version_changes_when_region_borders_change_in_place(self):
        before = self.version()

        # A savepoint gives the update its own (sub)transaction id, as a
        # separate request would in production.
        with transaction.atomic():
            borders = GeoPolygon.objects.get(pk=self.region.borders_id)
            borders.geom = MultiPolygon(Polygon.from_bbox((0, 0, 2, 2)))
            borders.save()

        self.assertNotEqual(self.version(), before)

    def test_version_changes_when_region_is_modified(self):
        before = self.version()

        Region.objects.filter(pk=self.region.pk).update(
            name="Renamed Region",
            lastmodified_at=timezone.now() + timedelta(seconds=5),
        )

        self.assertNotEqual(self.version(), before)

    def test_version_changes_on_region_edits_within_one_second(self):
        first_edit = timezone.now().replace(microsecond=100_000) + timedelta(seconds=5)
        Region.objects.filter(pk=self.region.pk).update(
            name="North", lastmodified_at=first_edit
        )
        before = self.version()

        Region.objects.filter(pk=self.region.pk).update(
            name="East", lastmodified_at=first_edit.replace(microsecond=800_000)
        )

        self.assertNotEqual(self.version(), before)

    def test_version_rotates_on_catchment_region_border_change_in_place(self):
        """The GeoJSON also ships pilot polygons built from catchment region
        borders, so in-place border edits must rotate the version."""
        catchment_region = Region.objects.create(
            name="TBN Region", publication_status="published"
        )
        catchment_region.geom = MultiPolygon(Polygon.from_bbox((3, 3, 4, 4)))
        catchment_region.save()
        catchment = Catchment.objects.create(
            name="TBN Catchment",
            region=catchment_region,
            publication_status="published",
        )
        Showcase.objects.filter(region=self.region).update(catchment=catchment)
        before = self.version()

        with transaction.atomic():
            borders = GeoPolygon.objects.get(pk=catchment_region.borders_id)
            borders.geom = MultiPolygon(Polygon.from_bbox((3, 3, 5, 5)))
            borders.save()

        self.assertNotEqual(self.version(), before)

    def test_version_rotates_when_catchment_is_modified(self):
        catchment = Catchment.objects.create(
            name="TBN Catchment",
            region=self.region,
            publication_status="published",
        )
        Showcase.objects.filter(region=self.region).update(catchment=catchment)
        before = self.version()

        Catchment.objects.filter(pk=catchment.pk).update(
            name="Renamed Catchment",
            lastmodified_at=timezone.now() + timedelta(seconds=5),
        )

        self.assertNotEqual(self.version(), before)

    def test_version_rotates_on_catchment_reassignment(self):
        other_region = Region.objects.create(
            name="Other TBN Region", publication_status="published"
        )
        other_catchment = Catchment.objects.create(
            name="Other Catchment",
            region=other_region,
            publication_status="published",
        )
        before = self.version()

        showcase = Showcase.objects.get(region=self.region)
        showcase.catchment = other_catchment
        showcase.save()

        self.assertNotEqual(self.version(), before)

    def _two_catchment_pilots(self):
        """Two showcases, each with its own published catchment; the first
        catchment carries the older modification time."""
        older, newer = (
            Catchment.objects.create(
                name=name, region=self.region, publication_status="published"
            )
            for name in ("Older Catchment", "Newer Catchment")
        )
        now = timezone.now()
        Catchment.objects.filter(pk=older.pk).update(
            lastmodified_at=now - timedelta(hours=2)
        )
        Catchment.objects.filter(pk=newer.pk).update(
            lastmodified_at=now - timedelta(hours=1)
        )
        Showcase.objects.filter(region=self.region).update(catchment=older)
        Showcase.objects.create(
            name="Second Showcase",
            region=self.region,
            catchment=newer,
            publication_status="published",
        )
        older.refresh_from_db()
        return older, newer

    def test_version_rotates_when_non_latest_catchment_changes(self):
        """Max aggregates miss edits to a row below the latest timestamp."""
        older, _ = self._two_catchment_pilots()
        before = self.version()

        with transaction.atomic():
            Catchment.objects.filter(pk=older.pk).update(
                name="Renamed Older Catchment",
                lastmodified_at=older.lastmodified_at + timedelta(minutes=1),
            )

        self.assertNotEqual(self.version(), before)

    def test_version_rotates_when_non_latest_fallback_region_changes(self):
        other_region = Region.objects.create(
            name="Other Region", publication_status="published"
        )
        Showcase.objects.create(
            name="Other Showcase",
            region=other_region,
            publication_status="published",
        )
        older_mod = timezone.now() - timedelta(hours=2)
        Region.objects.filter(pk=self.region.pk).update(lastmodified_at=older_mod)
        before = self.version()

        with transaction.atomic():
            Region.objects.filter(pk=self.region.pk).update(
                name="Renamed Region",
                lastmodified_at=older_mod + timedelta(minutes=1),
            )

        self.assertNotEqual(self.version(), before)

    def test_version_timestamp_carries_pilot_region_schema_salt(self):
        from ..viewsets import ShowcaseViewSet

        self.assertIn("pilot-regions-v1", ShowcaseViewSet()._version_timestamp({}))

    def test_version_timestamp_carries_code_label_schema_salt(self):
        from ..viewsets import ShowcaseViewSet

        self.assertIn("code-labels-v1", ShowcaseViewSet()._version_timestamp({}))

import json
from datetime import date, timedelta
from urllib.parse import urlencode

from django.db.models import signals
from django.db.models.signals import post_save
from django.forms.formsets import BaseFormSet
from django.http import JsonResponse
from django.http.request import MultiValueDict, QueryDict
from django.test import RequestFactory
from django.urls import reverse
from factory.django import mute_signals
from mock import Mock

from case_studies.soilcom.models import WasteFlyer, check_url_valid
from distributions.models import TemporalDistribution, Timestep
from maps.models import (
    GeoDataset,
    MapConfiguration,
    MapLayerConfiguration,
    MapLayerStyle,
    Region,
)
from materials.models import Material, MaterialCategory, Sample, SampleSeries
from utils.properties.models import Property, Unit
from utils.tests.testcases import AbstractTestCases, ViewWithPermissionsTestCase

from .. import views
from ..forms import BaseWasteFlyerUrlFormSet, CollectionModelForm
from ..models import (
    AggregatedCollectionPropertyValue,
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionPropertyValue,
    CollectionSeason,
    CollectionSystem,
    Collector,
    FeeSystem,
    WasteCategory,
    WasteComponent,
    WasteFlyer,
    WasteStream,
)


def setUpModule():
    post_save.disconnect(check_url_valid, sender=WasteFlyer)


def tearDownModule():
    post_save.connect(check_url_valid, sender=WasteFlyer)


# ----------- Collector CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectorCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True

    model = Collector

    view_dashboard_name = "wastecollection-dashboard"
    view_create_name = "collector-create"
    view_modal_create_name = "collector-create-modal"
    view_published_list_name = "collector-list"
    view_private_list_name = "collector-list-owned"
    view_detail_name = "collector-detail"
    view_modal_detail_name = "collector-detail-modal"
    view_update_name = "collector-update"
    view_modal_update_name = "collector-update-modal"
    view_delete_name = "collector-delete-modal"

    create_object_data = {"name": "Test Collector"}
    update_object_data = {"name": "Updated Test Collector"}


# ----------- Collection System CRUD -----------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionSystemCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True

    model = CollectionSystem

    view_dashboard_name = "wastecollection-dashboard"
    view_create_name = "collectionsystem-create"
    view_modal_create_name = "collectionsystem-create-modal"
    view_published_list_name = "collectionsystem-list"
    view_private_list_name = "collectionsystem-list-owned"
    view_detail_name = "collectionsystem-detail"
    view_modal_detail_name = "collectionsystem-detail-modal"
    view_update_name = "collectionsystem-update"
    view_modal_update_name = "collectionsystem-update-modal"
    view_delete_name = "collectionsystem-delete-modal"

    create_object_data = {"name": "Test Collection System"}
    update_object_data = {"name": "Updated Test Collection System"}


# ----------- Waste Category CRUD --------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteCategoryCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True

    model = WasteCategory

    view_dashboard_name = "wastecollection-dashboard"
    view_create_name = "wastecategory-create"
    view_modal_create_name = "wastecategory-create-modal"
    view_published_list_name = "wastecategory-list"
    view_private_list_name = "wastecategory-list-owned"
    view_detail_name = "wastecategory-detail"
    view_modal_detail_name = "wastecategory-detail-modal"
    view_update_name = "wastecategory-update"
    view_modal_update_name = "wastecategory-update-modal"
    view_delete_name = "wastecategory-delete-modal"

    create_object_data = {"name": "Test Waste Category"}
    update_object_data = {"name": "Updated Test Waste Category"}


# ----------- Waste Component CRUD -------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteComponentCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True

    model = WasteComponent

    view_dashboard_name = "wastecollection-dashboard"
    view_create_name = "wastecomponent-create"
    view_modal_create_name = "wastecomponent-create-modal"
    view_published_list_name = "wastecomponent-list"
    view_private_list_name = "wastecomponent-list-owned"
    view_detail_name = "wastecomponent-detail"
    view_modal_detail_name = "wastecomponent-detail-modal"
    view_update_name = "wastecomponent-update"
    view_modal_update_name = "wastecomponent-update-modal"
    view_delete_name = "wastecomponent-delete-modal"

    create_object_data = {"name": "Test Waste Component"}
    update_object_data = {"name": "Updated Test Waste Component"}

    @classmethod
    def create_related_objects(cls):
        MaterialCategory.objects.create(name="Biowaste component")
        return {}

    @classmethod
    def create_published_object(cls):
        # This method is overridden to give another name to the published object because of the unique name constraint
        data = cls.create_object_data.copy()
        data["name"] = f'{data["name"]} (published)'
        data["publication_status"] = "published"
        data.update(cls.related_objects)
        return cls.model.objects.create(owner=cls.owner_user, **data)


# ----------- Fee System CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class FeeSystemCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = FeeSystem

    view_dashboard_name = "wastecollection-dashboard"
    view_create_name = "feesystem-create"
    view_published_list_name = "feesystem-list"
    view_private_list_name = "feesystem-list-owned"
    view_detail_name = "feesystem-detail"
    view_update_name = "feesystem-update"
    view_delete_name = "feesystem-delete-modal"

    create_object_data = {"name": "Test Fee System"}
    update_object_data = {"name": "Updated Test Fee System"}


# ----------- WasteFlyer CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class WasteFlyerCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    create_view = False
    modal_detail_view = True
    update_view = False
    delete_view = False

    model = WasteFlyer

    view_dashboard_name = "wastecollection-dashboard"
    view_published_list_name = "wasteflyer-list"
    view_private_list_name = "wasteflyer-list-owned"
    view_detail_name = "wasteflyer-detail"
    view_modal_detail_name = "wasteflyer-detail-modal"

    create_object_data = {"url": "https://www.crud-test-flyer.org"}

    # @classmethod
    # def setUpClass(cls):
    #     super().setUpClass()
    #     post_save.disconnect(check_url_valid, sender=WasteFlyer)

    # @classmethod
    # def tearDownClass(cls):
    #     post_save.connect(check_url_valid, sender=WasteFlyer)
    #     super().tearDownClass()

    def test_list_unpublished_contains_check_urls_button_for_authenticated_owner(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse("wasteflyer-list-owned"))
        self.assertContains(response, "check urls")

    def test_list_published_contains_check_urls_button_for_staff_user(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("wasteflyer-list"))
        self.assertContains(response, "check urls")

    def test_detail_view_unpublished_contains_check_url_button_for_owner(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_detail_url(self.unpublished_object.pk))
        self.assertContains(response, "check url")

    def test_detail_view_published_contains_check_url_button_for_owner(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertContains(response, "check url")

    def test_detail_view_published_doesnt_contain_check_url_button_for_anonymous(self):
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertNotContains(response, "check url")

    def test_detail_view_published_doesnt_contain_check_url_button_for_non_owner(self):
        self.client.force_login(self.non_owner_user)
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertNotContains(response, "check url")


# ----------- Collection Frequency CRUD --------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionFrequencyCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True

    model = CollectionFrequency

    view_dashboard_name = "wastecollection-dashboard"
    view_create_name = "collectionfrequency-create"
    view_published_list_name = "collectionfrequency-list"
    view_private_list_name = "collectionfrequency-list-owned"
    view_detail_name = "collectionfrequency-detail"
    view_modal_detail_name = "collectionfrequency-detail-modal"
    view_update_name = "collectionfrequency-update"
    view_modal_update_name = "collectionfrequency-update-modal"
    view_delete_name = "collectionfrequency-delete-modal"

    create_object_data = {"name": "Test Frequency"}
    update_object_data = {"name": "Updated Test Frequency"}

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.distribution = TemporalDistribution.objects.get(name="Months of the year")
        cls.january = Timestep.objects.get(name="January")
        cls.may = Timestep.objects.get(name="May")
        cls.june = Timestep.objects.get(name="June")
        cls.december = Timestep.objects.get(name="December")
        season_1 = CollectionSeason.objects.create(
            distribution=cls.distribution,
            first_timestep=cls.january,
            last_timestep=cls.may,
        )
        season_2 = CollectionSeason.objects.create(
            distribution=cls.distribution,
            first_timestep=cls.june,
            last_timestep=cls.december,
        )
        cls.options_1 = CollectionCountOptions.objects.create(
            frequency=cls.unpublished_object,
            season=season_1,
            standard=100,
            option_1=150,
        )
        cls.options_2 = CollectionCountOptions.objects.create(
            frequency=cls.unpublished_object, season=season_2, standard=150
        )

    def related_objects_post_data(self):
        data = {
            "name": "Test Frequency with Seasons",
            "type": "Fixed-Seasonal",
            "form-INITIAL_FORMS": 1,
            "form-TOTAL_FORMS": 2,
            "form-0-distribution": self.distribution.id,
            "form-0-first_timestep": self.january.id,
            "form-0-last_timestep": self.may.id,
            "form-0-standard": 150,
            "form-0-option_1": "",
            "form-0-option_2": "",
            "form-0-option_3": "",
            "form-1-distribution": self.distribution.id,
            "form-1-first_timestep": self.june.id,
            "form-1-last_timestep": self.december.id,
            "form-1-standard": 200,
            "form-1-option_1": "",
            "form-1-option_2": "",
            "form-1-option_3": "",
        }
        return data

    def test_get_formset_queryset_returns_whole_year_season(self):
        request = RequestFactory().get(self.get_create_url())
        request.user = self.staff_user
        view = views.FrequencyCreateView()
        view.setup(request)
        months = TemporalDistribution.objects.get(name="Months of the year")
        first = months.timestep_set.get(name="January")
        last = months.timestep_set.get(name="December")
        initial = list(
            CollectionSeason.objects.filter(
                distribution=months, first_timestep=first, last_timestep=last
            ).values("distribution", "first_timestep", "last_timestep")
        )
        self.assertListEqual(initial, view.get_formset_initial())

    def test_post_with_valid_data_creates_and_relates_seasons(self):
        self.client.force_login(self.staff_user)
        data = {
            "name": "Test Frequency with Seasons",
            "type": "Fixed-Seasonal",
            "form-INITIAL_FORMS": 1,
            "form-TOTAL_FORMS": 2,
            "form-0-distribution": self.distribution.id,
            "form-0-first_timestep": Timestep.objects.get(
                distribution=self.distribution, name="January"
            ).id,
            "form-0-last_timestep": Timestep.objects.get(
                distribution=self.distribution, name="April"
            ).id,
            "form-1-distribution": self.distribution.id,
            "form-1-first_timestep": Timestep.objects.get(
                distribution=self.distribution, name="May"
            ).id,
            "form-1-last_timestep": Timestep.objects.get(
                distribution=self.distribution, name="December"
            ).id,
        }
        response = self.client.post(self.get_create_url(), data)
        self.assertEqual(response.status_code, 302)
        frequency = CollectionFrequency.objects.get(name="Test Frequency with Seasons")
        seasons = [
            CollectionSeason.objects.get(
                first_timestep__name="January", last_timestep__name="April"
            ),
            CollectionSeason.objects.get(
                first_timestep__name="May", last_timestep__name="December"
            ),
        ]
        self.assertListEqual(
            seasons, list(frequency.seasons.order_by("first_timestep__order"))
        )

    def test_form_contains_all_initials(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_update_url(self.unpublished_object.pk))
        form = response.context["form"]
        expected = {
            "name": self.unpublished_object.name,
            "type": self.unpublished_object.type,
            "description": self.unpublished_object.description,
        }
        self.assertDictEqual(expected, form.initial)

    def test_formset_contains_all_initials(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_update_url(self.unpublished_object.pk))
        formset = response.context["formset"]
        expected = [
            {
                "distribution": self.distribution,
                "first_timestep": self.january,
                "last_timestep": self.may,
                "standard": 100,
                "option_1": 150,
                "option_2": None,
                "option_3": None,
            },
            {
                "distribution": self.distribution,
                "first_timestep": self.june,
                "last_timestep": self.december,
                "standard": 150,
                "option_1": None,
                "option_2": None,
                "option_3": None,
            },
        ]
        self.assertListEqual(expected, formset.initial)

    def test_post_http_302_options_are_changed_on_save(self):
        self.client.force_login(self.owner_user)
        url = self.get_update_url(self.unpublished_object.pk)
        data = self.related_objects_post_data()
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.options_1.refresh_from_db()
        self.options_2.refresh_from_db()
        self.assertEqual(150, self.options_1.standard)
        self.assertIsNone(self.options_1.option_1)
        self.assertIsNone(self.options_1.option_2)
        self.assertIsNone(self.options_1.option_3)
        self.assertEqual(200, self.options_2.standard)
        self.assertIsNone(self.options_2.option_1)
        self.assertIsNone(self.options_2.option_2)
        self.assertIsNone(self.options_2.option_3)


# ----------- CollectionPropertyValue CRUD -----------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionPropertyValueCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    public_list_view = False
    private_list_view = False

    model = CollectionPropertyValue

    view_dashboard_name = "wastecollection-dashboard"
    view_create_name = "collectionpropertyvalue-create"
    view_detail_name = "collectionpropertyvalue-detail"
    view_update_name = "collectionpropertyvalue-update"
    view_delete_name = "collectionpropertyvalue-delete-modal"

    create_object_data = {"average": 123.5, "standard_deviation": 12.54, "year": 2025}
    update_object_data = {"average": 456.7, "standard_deviation": 23.45, "year": 2025}

    @classmethod
    def create_related_objects(cls):
        return {
            "collection": Collection.objects.create(
                owner=cls.owner_user, name="Test Collection"
            ),
            "property": Property.objects.create(name="Test Property"),
            "unit": Unit.objects.create(name="Test Unit"),
        }

    def get_delete_success_url(self, publication_status=None):
        return reverse(
            "collection-detail", kwargs={"pk": self.related_objects["collection"].pk}
        )


# ----------- AggregatedCollectionPropertyValue CRUD -------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AggregatedCollectionPropertyValueCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    public_list_view = False
    private_list_view = False

    model = AggregatedCollectionPropertyValue

    view_dashboard_name = "wastecollection-dashboard"
    view_create_name = "aggregatedcollectionpropertyvalue-create"
    view_detail_name = "aggregatedcollectionpropertyvalue-detail"
    view_update_name = "aggregatedcollectionpropertyvalue-update"
    view_delete_name = "aggregatedcollectionpropertyvalue-delete-modal"

    create_object_data = {"year": 2025, "average": 123.5, "standard_deviation": 12.54}
    update_object_data = {"year": 2025, "average": 456.7, "standard_deviation": 23.45}

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.related_collections = [
            Collection.objects.create(name="Test Collection 1"),
            Collection.objects.create(name="Test Collection 2"),
        ]
        cls.published_object.collections.set(cls.related_collections)
        cls.unpublished_object.collections.set(cls.related_collections)

    @classmethod
    def create_related_objects(cls):
        return {
            "property": Property.objects.create(name="Test Property"),
            "unit": Unit.objects.create(name="Test Unit"),
        }

    def related_objects_post_data(self):
        data = super().related_objects_post_data()
        data.update(
            {
                "collections": [
                    Collection.objects.create(name="Test Collection 3").pk,
                    Collection.objects.create(name="Test Collection 4").pk,
                ]
            }
        )
        return data

    def get_delete_success_url(self, publication_status=None):
        related_ids = [collection.id for collection in self.related_collections]
        base_url = reverse("collection-list")
        query_string = urlencode([("id", rid) for rid in related_ids])
        return f"{base_url}?{query_string}"


# ----------- Collection Catchment CRUD --------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionCatchmentCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    model = CollectionCatchment
    model_add_permission = "add_catchment"

    view_dashboard_name = "wastecollection-dashboard"
    view_published_list_name = "collectioncatchment-list"
    view_private_list_name = "collectioncatchment-list-owned"
    view_create_name = "collectioncatchment-create"
    view_detail_name = "collectioncatchment-detail"
    view_update_name = "collectioncatchment-update"
    view_delete_name = "collectioncatchment-delete-modal"

    delete_success_url_name = "catchment-list"

    create_object_data = {"name": "Test Catchment"}
    update_object_data = {"name": "Updated Test Catchment"}

    @classmethod
    def create_related_objects(cls):
        return {"region": Region.objects.create(name="Test Region")}

    def test_collectioncatchment_template_is_used(self):
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertTemplateUsed(response, "soilcom/collectioncatchment_detail.html")

    def test_list_view_published_as_authenticated_owner(self):
        if not self.public_list_view:
            self.skipTest("List view is not enabled for this test case.")
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_list_url(publication_status="published"))
        self.assertEqual(response.status_code, 200)
        if self.dashboard_view:
            self.assertContains(response, self.get_dashboard_url())
        if self.create_view:
            self.assertContains(
                response, self.get_create_url()
            )  # This is the custom line
        if self.private_list_view:
            self.assertContains(
                response, self.get_list_url(publication_status="private")
            )

    def test_list_view_published_as_authenticated_non_owner(self):
        if not self.public_list_view:
            self.skipTest("List view is not enabled for this test case.")
        self.client.force_login(self.non_owner_user)
        response = self.client.get(self.get_list_url(publication_status="published"))
        self.assertEqual(response.status_code, 200)
        if self.dashboard_view:
            self.assertContains(response, self.get_dashboard_url())
        if self.create_view:
            self.assertContains(
                response, self.get_create_url()
            )  # This is the custom line
        if self.private_list_view:
            self.assertContains(
                response, self.get_list_url(publication_status="private")
            )

    def test_list_view_private_as_authenticated_owner(self):
        if not self.private_list_view:
            self.skipTest("List view is not enabled for this test case")
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_list_url(publication_status="private"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<th>Public</th>")
        if self.dashboard_view:
            self.assertContains(response, self.get_dashboard_url())
        if self.create_view:
            self.assertContains(
                response, self.get_create_url()
            )  # This is the custom line
        if self.public_list_view:
            self.assertContains(
                response, self.get_list_url(publication_status="published")
            )

    def test_list_view_private_as_authenticated_non_owner(self):
        if not self.private_list_view:
            self.skipTest("List view is not enabled for this test case")
        self.client.force_login(self.non_owner_user)
        response = self.client.get(self.get_list_url(publication_status="private"))
        self.assertEqual(response.status_code, 200)
        if self.dashboard_view:
            self.assertContains(response, self.get_dashboard_url())
        if self.create_view:
            self.assertContains(
                response, self.get_create_url()
            )  # This is the custom line
        if self.public_list_view:
            self.assertContains(
                response, self.get_list_url(publication_status="published")
            )

    # -----------------------
    # CreateView Test Cases
    # -----------------------

    def test_create_view_post_as_authenticated_with_permission(self):
        self.skipTest("Post method is not implemented for this view.")

    def test_create_view_post_as_staff_user(self):
        self.skipTest("Post method is not implemented for this view.")


# ----------- Collection CRUD ------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_detail_view = True

    model = Collection

    view_dashboard_name = "wastecollection-dashboard"
    view_create_name = "collection-create"
    view_published_list_name = "collection-list"
    view_private_list_name = "collection-list-owned"
    view_detail_name = "collection-detail"
    view_modal_detail_name = "collection-detail-modal"
    view_update_name = "collection-update"
    view_delete_name = "collection-delete-modal"

    create_object_data = {
        "name": "Test Collection",
        "description": "The original collection",
        "connection_type": "VOLUNTARY",
        "valid_from": date.today(),
        "valid_until": date.today() + timedelta(days=365),
    }
    update_object_data = {
        "name": "Updated Test Collection",
        "connection_type": "VOLUNTARY",
        "description": "This has been updated",
    }

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with mute_signals(signals.post_save):
            cls.flyer = WasteFlyer.objects.create(
                abbreviation="WasteFlyer123", url="https://www.test-flyer.org"
            )
            cls.flyer2 = WasteFlyer.objects.create(
                abbreviation="WasteFlyer234", url="https://www.rest-flyer.org"
            )
        cls.unpublished_object.flyers.add(cls.flyer)
        cls.unpublished_object.flyers.add(cls.flyer2)
        cls.published_object.flyers.add(cls.flyer)
        cls.published_object.flyers.add(cls.flyer2)

    @classmethod
    def create_related_objects(cls):
        MaterialCategory.objects.create(name="Biowaste component")
        catchment = CollectionCatchment.objects.create(name="Test catchment")
        collector = Collector.objects.create(name="Test collector")
        collection_system = CollectionSystem.objects.create(name="Test system")
        waste_category = WasteCategory.objects.create(name="Test category")
        cls.allowed_material_1 = WasteComponent.objects.create(
            name="Allowed material 1"
        )
        cls.allowed_material_2 = WasteComponent.objects.create(
            name="Allowed material 2"
        )
        cls.forbidden_material_1 = WasteComponent.objects.create(
            name="Forbidden material 1"
        )
        cls.forbidden_material_2 = WasteComponent.objects.create(
            name="Forbidden material 2"
        )
        waste_stream = WasteStream.objects.create(
            name="Test waste stream",
            category=waste_category,
        )
        waste_stream.allowed_materials.add(cls.allowed_material_1)
        waste_stream.allowed_materials.add(cls.allowed_material_2)
        waste_stream.forbidden_materials.add(cls.forbidden_material_1)
        waste_stream.forbidden_materials.add(cls.forbidden_material_2)
        frequency = CollectionFrequency.objects.create(name="Test Frequency")
        Collection.objects.create(
            catchment=catchment,
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
            frequency=frequency,
            valid_from=date.today() - timedelta(days=365),
            valid_until=date.today() - timedelta(days=1),
            description="Predecessor Collection 1",
        )
        Collection.objects.create(
            catchment=catchment,
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
            frequency=frequency,
            valid_from=date.today() - timedelta(days=365),
            valid_until=date.today() - timedelta(days=1),
            description="Predecessor Collection 2",
        )
        # Create a bunch of unused outdated collections
        for i in range(12):
            Collection.objects.create(
                catchment=catchment,
                collector=collector,
                collection_system=collection_system,
                waste_stream=waste_stream,
                frequency=frequency,
                valid_from=date.today() - timedelta(days=365),
                valid_until=date.today() - timedelta(days=1),
                description=f"Oudated Collection {i}",
                publication_status="published",
            )
        return {
            "catchment": catchment,
            "collector": collector,
            "collection_system": collection_system,
            "waste_stream": waste_stream,
            "frequency": frequency,
        }

    @classmethod
    def create_published_object(cls):
        collection = super().create_published_object()
        collection.add_predecessor(
            Collection.objects.get(description="Predecessor Collection 1")
        )
        collection.add_predecessor(
            Collection.objects.get(description="Predecessor Collection 2")
        )
        return collection

    def related_objects_post_data(self):
        data = super().related_objects_post_data()
        data.update(
            {
                "waste_category": WasteCategory.objects.get(name="Test category").pk,
                "valid_from": date.today(),
                "form-TOTAL_FORMS": 0,
                "form-INITIAL_FORMS": 0,
            }
        )
        return data

    def get_delete_success_url(self, publication_status=None):
        return f"{reverse('collection-list-owned')}?valid_on={date.today()}"

    def test_post_get_formset_kwargs_fetches_correct_parent_object(self):
        request = RequestFactory().post(self.get_create_url())
        request.user = self.staff_user
        view = views.CollectionCreateView()
        view.setup(request)
        view.object = self.unpublished_object
        formset_kwargs = view.get_formset_kwargs()
        self.assertEqual(formset_kwargs["parent_object"], self.unpublished_object)

    def test_get_formset_has_correct_queryset(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.get_create_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["formset"].forms), 1)

    def test_post_with_missing_data_errors(self):
        self.client.force_login(self.staff_user)
        response = self.client.post(
            self.get_create_url(), data={"connection_rate_year": 123}
        )
        self.assertEqual(response.status_code, 200)

        error_msg = "This field is required."
        self.assertTrue(error_msg in response.context["form"].errors["catchment"])
        self.assertTrue(error_msg in response.context["form"].errors["collector"])
        self.assertTrue(
            error_msg in response.context["form"].errors["collection_system"]
        )
        self.assertTrue(error_msg in response.context["form"].errors["waste_category"])

    def test_post_with_valid_form_data(self):
        self.assertEqual(Collection.objects.count(), 1)
        self.client.force_login(self.staff_user)
        response = self.client.post(
            self.get_create_url(),
            data={
                "catchment": CollectionCatchment.objects.first().id,
                "collector": Collector.objects.first().id,
                "collection_system": CollectionSystem.objects.first().id,
                "waste_category": WasteCategory.objects.first().id,
                "connection_type": "VOLUNTARY",
                "allowed_materials": [
                    self.allowed_material_1.id,
                    self.allowed_material_2.id,
                ],
                "forbidden_materials": [
                    self.forbidden_material_1.id,
                    self.forbidden_material_2.id,
                ],
                "frequency": CollectionFrequency.objects.first().id,
                "valid_from": date(2020, 1, 1),
                "description": "This is a test case that should pass!",
                "form-INITIAL_FORMS": "0",
                "form-TOTAL_FORMS": "2",
                "form-0-url": "https://www.test-flyer.org",
                "form-0-id": "",
                "form-1-url": "",
                "form-1-id": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Collection.objects.count(), 2)

    def test_post_with_unspecified_allowed_materials_creates_generic_waste_stream(self):
        self.client.force_login(self.staff_user)
        data = {
            "catchment": CollectionCatchment.objects.first().id,
            "collector": Collector.objects.first().id,
            "collection_system": CollectionSystem.objects.first().id,
            "waste_category": WasteCategory.objects.first().id,
            "connection_type": "VOLUNTARY",
            "allowed_materials": [],
            "forbidden_materials": [
                self.forbidden_material_1.id,
                self.forbidden_material_2.id,
            ],
            "frequency": CollectionFrequency.objects.first().id,
            "valid_from": date(2020, 1, 1),
            "description": "This is a test case that should pass!",
            "form-INITIAL_FORMS": "0",
            "form-TOTAL_FORMS": "2",
            "form-0-url": "https://www.test-flyer.org",
            "form-0-id": "",
            "form-1-url": "",
            "form-1-id": "",
        }
        initial_count = Collection.objects.count()
        response = self.client.post(self.get_create_url(), data=data, follow=True)
        self.assertEqual(Collection.objects.count(), initial_count + 1)
        new_collection = Collection.objects.get(description=data["description"])
        self.assertRedirects(
            response, reverse("collection-detail", kwargs={"pk": new_collection.pk})
        )
        self.assertFalse(new_collection.waste_stream.allowed_materials.exists())

    def test_list_view_published_as_anonymous(self):
        response = self.client.get(self.get_list_url(), follow=True)
        redirect_url = f'{self.get_list_url()}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertNotContains(response, self.get_create_url(), status_code=200)

    def test_list_view_published_as_authenticated_owner(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_list_url(), follow=True)
        redirect_url = f'{self.get_list_url()}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertNotContains(response, self.get_create_url(), status_code=200)

    def test_list_view_published_as_authenticated_non_owner(self):
        self.client.force_login(self.non_owner_user)
        response = self.client.get(self.get_list_url(), follow=True)
        redirect_url = f'{self.get_list_url()}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertNotContains(response, self.get_create_url(), status_code=200)

    def test_list_view_published_as_staff_user(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(self.get_list_url(), follow=True)
        redirect_url = f'{self.get_list_url()}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertContains(response, self.get_create_url(), status_code=200)

    def test_list_view_private_as_authenticated_owner(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(
            self.get_list_url(publication_status="private"), follow=True
        )
        redirect_url = f'{self.get_list_url(publication_status="private")}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertContains(response, self.get_dashboard_url())
        self.assertNotContains(response, self.get_create_url())
        self.assertContains(response, self.get_list_url(publication_status="published"))

    def test_list_view_private_as_authenticated_non_owner(self):
        self.client.force_login(self.non_owner_user)
        response = self.client.get(
            self.get_list_url(publication_status="private"), follow=True
        )
        redirect_url = f'{self.get_list_url(publication_status="private")}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertContains(response, self.get_dashboard_url())
        self.assertNotContains(response, self.get_create_url())
        self.assertContains(response, self.get_list_url(publication_status="published"))

    def test_list_view_private_as_authenticated_staff_user(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(
            self.get_list_url(publication_status="private"), follow=True
        )
        redirect_url = f'{self.get_list_url(publication_status="private")}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertContains(response, self.get_dashboard_url())
        self.assertContains(response, self.get_create_url())
        self.assertContains(response, self.get_list_url(publication_status="published"))

    def test_list_view_published_pagination_works_without_further_query_parameters(
        self,
    ):
        query_params = urlencode(
            {"valid_until": date.today() - timedelta(days=2), "page": 2}
        )
        response = self.client.get(f"{self.get_list_url()}?{query_params}")
        self.assertEqual(response.status_code, 200)

    def test_list_view_published_initial_queryset_only_contains_current_collections(
        self,
    ):
        response = self.client.get(self.get_list_url(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["object_list"]), 1)
        self.assertQuerySetEqual(
            Collection.objects.filter(publication_status="published").exclude(
                valid_until__lt=date.today()
            ),
            response.context["object_list"],
        )

    def test_template_contains_predecessor_collections(self):
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertContains(
            response,
            Collection.objects.get(description="Predecessor Collection 1").name,
        )
        self.assertContains(
            response,
            Collection.objects.get(description="Predecessor Collection 2").name,
        )

    def test_template_contains_flyer_url(self):
        response = self.client.get(self.get_detail_url(self.published_object.pk))
        self.assertContains(response, "https://www.test-flyer.org")

    def test_uses_custom_template(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_update_url(self.unpublished_object.pk))
        self.assertTemplateUsed(response, "soilcom/collection_form.html")

    def test_get_get_formset_kwargs(self):
        request = RequestFactory().get(self.get_update_url(self.unpublished_object.pk))
        request.user = self.owner_user
        view = views.CollectionUpdateView()
        view.setup(request)
        view.kwargs = {"pk": self.unpublished_object.pk}
        view.object = self.unpublished_object
        view.relation_field_name = "flyers"
        expected_formset_kwargs = {
            "initial": [{"url": self.flyer.url}, {"url": self.flyer2.url}],
            "parent_object": self.unpublished_object,
            "owner": self.owner_user,
            "relation_field_name": view.relation_field_name,
        }
        self.assertDictEqual(expected_formset_kwargs, view.get_formset_kwargs())

    def test_post_get_formset_kwargs(self):
        kwargs = {"pk": self.unpublished_object.pk}
        data = {
            "form-INITIAL_FORMS": "0",
            "form-TOTAL_FORMS": "2",
            "form-0-url": "https://www.test-flyer.org",
            "form-1-url": "https://www.best-flyer.org",
        }
        request = RequestFactory().post(
            self.get_update_url(self.unpublished_object.pk), data=data
        )
        request.user = self.owner_user
        view = views.CollectionUpdateView()
        view.setup(request)
        view.kwargs = kwargs
        view.object = self.unpublished_object
        view.relation_field_name = "flyers"
        query_dict = QueryDict("", mutable=True)
        query_dict.update(data)
        expected_formset_kwargs = {
            "parent_object": self.unpublished_object,
            "owner": self.owner_user,
            "initial": [{"url": self.flyer.url}, {"url": self.flyer2.url}],
            "data": query_dict,
            "relation_field_name": view.relation_field_name,
        }
        self.assertDictEqual(expected_formset_kwargs, view.get_formset_kwargs())

    def test_get_get_formset(self):
        request = RequestFactory().get(self.get_update_url(self.unpublished_object.pk))
        request.user = self.owner_user
        view = views.CollectionUpdateView()
        view.setup(request)
        view.kwargs = {"pk": self.unpublished_object.pk}
        view.object = self.unpublished_object
        formset = view.get_formset()
        self.assertIsInstance(formset, BaseWasteFlyerUrlFormSet)
        self.assertEqual(2, formset.initial_form_count())

    def test_post_get_formset(self):
        data = {
            "form-INITIAL_FORMS": "0",
            "form-TOTAL_FORMS": "2",
            "form-0-url": "https://www.test-flyer.org",
            "form-1-url": "https://www.best-flyer.org",
        }
        request = RequestFactory().post(
            self.get_update_url(self.unpublished_object.pk), data=data
        )
        request.user = self.owner_user
        view = views.CollectionUpdateView()
        view.setup(request)
        view.kwargs = {"pk": self.unpublished_object.pk}
        view.object = self.unpublished_object
        formset = view.get_formset()
        self.assertIsInstance(formset, BaseWasteFlyerUrlFormSet)

    def test_context_contains_form_and_formset(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_update_url(self.unpublished_object.pk))
        self.assertIsInstance(response.context["form"], CollectionModelForm)
        self.assertIsInstance(response.context["formset"], BaseFormSet)

    def test_post_with_missing_data_errors(self):
        self.client.force_login(self.owner_user)
        response = self.client.post(
            self.get_update_url(self.unpublished_object.pk),
            data={"connection_rate_year": 123},
        )
        self.assertEqual(response.status_code, 200)

        error_msg = "This field is required."
        self.assertTrue(error_msg in response.context["form"].errors["catchment"])
        self.assertTrue(error_msg in response.context["form"].errors["collector"])
        self.assertTrue(
            error_msg in response.context["form"].errors["collection_system"]
        )
        self.assertTrue(error_msg in response.context["form"].errors["waste_category"])

    def test_post_with_valid_form_data(self):
        self.client.force_login(self.owner_user)
        response = self.client.post(
            self.get_update_url(self.unpublished_object.pk),
            data={
                "catchment": CollectionCatchment.objects.first().id,
                "collector": Collector.objects.first().id,
                "collection_system": CollectionSystem.objects.first().id,
                "waste_category": WasteCategory.objects.first().id,
                "connection_type": "VOLUNTARY",
                "allowed_materials": [
                    self.allowed_material_1.id,
                    self.allowed_material_2.id,
                ],
                "forbidden_materials": [
                    self.forbidden_material_1.id,
                    self.forbidden_material_2.id,
                ],
                "frequency": CollectionFrequency.objects.first().id,
                "valid_from": date(2020, 1, 1),
                "description": "This is a test case that should pass!",
                "form-INITIAL_FORMS": "0",
                "form-TOTAL_FORMS": "2",
                "form-0-url": "https://www.test-flyer.org",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_post_without_allowed_materials(self):
        self.client.force_login(self.owner_user)
        response = self.client.post(
            self.get_update_url(self.unpublished_object.pk),
            data={
                "catchment": CollectionCatchment.objects.first().id,
                "collector": Collector.objects.first().id,
                "collection_system": CollectionSystem.objects.first().id,
                "waste_category": WasteCategory.objects.first().id,
                "connection_type": "VOLUNTARY",
                "allowed_materials": [
                    self.allowed_material_1.id,
                    self.allowed_material_2.id,
                ],
                "frequency": CollectionFrequency.objects.first().id,
                "valid_from": date(2020, 1, 1),
                "description": "This is a test case that should pass!",
                "form-INITIAL_FORMS": "2",
                "form-TOTAL_FORMS": "2",
                "form-0-url": "https://www.test-flyer.org",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_associated_flyers_are_displayed_as_initial_values_in_formset(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_update_url(self.unpublished_object.pk))
        expected_initial = [flyer.url for flyer in self.unpublished_object.flyers.all()]
        real_initial = [
            form.initial["url"] for form in response.context["formset"].initial_forms
        ]
        self.assertListEqual(expected_initial, real_initial)

    def test_new_flyers_are_created_from_unknown_urls(self):
        self.client.force_login(self.owner_user)
        data = {
            "catchment": self.unpublished_object.catchment.id,
            "collector": self.unpublished_object.collector.id,
            "collection_system": self.unpublished_object.collection_system.id,
            "waste_category": self.unpublished_object.waste_stream.category.id,
            "connection_type": "VOLUNTARY",
            "allowed_materials": [
                m.id
                for m in self.unpublished_object.waste_stream.allowed_materials.all()
            ],
            "forbidden_materials": [
                m.id
                for m in self.unpublished_object.waste_stream.forbidden_materials.all()
            ],
            "frequency": self.unpublished_object.frequency.id,
            "valid_from": date(2020, 1, 1),
            "description": self.unpublished_object.description,
            "form-INITIAL_FORMS": "1",
            "form-TOTAL_FORMS": "2",
            "form-0-url": "https://www.best-flyer.org",
            "form-1-url": "https://www.fest-flyer.org",
        }
        with mute_signals(signals.post_save):
            self.client.post(self.get_update_url(self.unpublished_object.pk), data=data)
        flyer = WasteFlyer.objects.get(url="https://www.fest-flyer.org")
        self.assertIsInstance(flyer, WasteFlyer)

    def test_regression_post_with_valid_data_doesnt_delete_unchanged_flyers(self):
        self.client.force_login(self.owner_user)
        data = {
            "catchment": self.unpublished_object.catchment.id,
            "collector": self.unpublished_object.collector.id,
            "collection_system": self.unpublished_object.collection_system.id,
            "waste_category": self.unpublished_object.waste_stream.category.id,
            "connection_type": "VOLUNTARY",
            "allowed_materials": [
                m.id
                for m in self.unpublished_object.waste_stream.allowed_materials.all()
            ],
            "forbidden_materials": [
                m.id
                for m in self.unpublished_object.waste_stream.forbidden_materials.all()
            ],
            "frequency": self.unpublished_object.frequency.id,
            "valid_from": self.unpublished_object.valid_from,
            "description": self.unpublished_object.description,
            "form-INITIAL_FORMS": "1",
            "form-TOTAL_FORMS": "2",
            "form-0-url": self.unpublished_object.flyers.first().url,
            "form-0-id": self.unpublished_object.flyers.first().id,
            "form-1-url": "https://www.fest-flyer.org",
            "form-1-id": "",
        }
        # The flyer with the url rest-flyer.org should be removed from the unpublished collection  by this. Remove it from the
        # published collection as well before the request so that the process for deleting orphaned flyers is evoked.
        rest_flyer = WasteFlyer.objects.get(url="https://www.rest-flyer.org")
        self.published_object.flyers.remove(rest_flyer)
        with mute_signals(post_save):
            response = self.client.post(
                self.get_update_url(self.unpublished_object.pk), data=data
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            WasteFlyer.objects.get(url="https://www.fest-flyer.org"),
            self.unpublished_object.flyers.all(),
        )
        self.assertIn(
            WasteFlyer.objects.get(url="https://www.test-flyer.org"),
            self.unpublished_object.flyers.all(),
        )
        self.assertEqual(WasteFlyer.objects.count(), 2)


class CollectionCopyViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_collection"
    url_name = "collection-copy"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        MaterialCategory.objects.create(name="Biowaste component")
        cls.allowed_material_1 = WasteComponent.objects.create(
            name="Allowed material 1"
        )
        cls.allowed_material_2 = WasteComponent.objects.create(
            name="Allowed material 2"
        )
        cls.forbidden_material_1 = WasteComponent.objects.create(
            name="Forbidden material 1"
        )
        cls.forbidden_material_2 = WasteComponent.objects.create(
            name="Forbidden material 2"
        )
        waste_stream = WasteStream.objects.create(
            name="Test waste stream",
            category=WasteCategory.objects.create(name="Test category"),
        )
        waste_stream.allowed_materials.add(cls.allowed_material_1)
        waste_stream.allowed_materials.add(cls.allowed_material_2)
        waste_stream.forbidden_materials.add(cls.forbidden_material_1)
        waste_stream.forbidden_materials.add(cls.forbidden_material_2)
        with mute_signals(signals.post_save):
            cls.flyer = WasteFlyer.objects.create(
                abbreviation="WasteFlyer123", url="https://www.test-flyer.org"
            )
            cls.flyer2 = WasteFlyer.objects.create(
                abbreviation="WasteFlyer234", url="https://www.fest-flyer.org"
            )
        frequency = CollectionFrequency.objects.create(name="Test Frequency")
        cls.collection = Collection.objects.create(
            name="collection1",
            catchment=CollectionCatchment.objects.create(name="Test catchment"),
            collector=Collector.objects.create(name="Test collector"),
            collection_system=CollectionSystem.objects.create(name="Test system"),
            waste_stream=waste_stream,
            frequency=frequency,
            description="This is a test case.",
        )
        cls.collection.flyers.add(cls.flyer)
        cls.collection.flyers.add(cls.flyer2)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_non_group_members(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_group_members(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_get_object(self):
        request = RequestFactory().get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        request.user = self.member
        view = views.CollectionCopyView()
        view.setup(request)
        view.kwargs = {"pk": self.collection.id}
        self.assertEqual(view.get_object(), self.collection)

    def test_get_get_formset_kwargs_fetches_initial_and_parent_object(self):
        request = RequestFactory().get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        view = views.CollectionCopyView()
        view.setup(request)
        view.kwargs = {"pk": self.collection.id}
        view.object = view.get_object()
        view.relation_field_name = "flyers"
        expected = {
            "initial": [{"url": self.flyer.url}, {"url": self.flyer2.url}],
            "parent_object": self.collection,
            "relation_field_name": view.relation_field_name,
        }
        self.assertDictEqual(expected, view.get_formset_kwargs())

    def test_get_get_formset_initial_fetches_urls_of_related_flyers(self):
        request = RequestFactory().get(
            reverse(self.url_name, kwargs={"pk": self.collection.pk})
        )
        request.user = self.member
        view = views.CollectionCopyView()
        view.setup(request)
        view.kwargs = {"pk": self.collection.pk}
        view.object = view.get_object()
        expected = [
            {"url": "https://www.test-flyer.org"},
            {"url": "https://www.fest-flyer.org"},
        ]
        self.assertListEqual(expected, view.get_formset_initial())

    def test_get_formset_has_correct_queryset(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            len(response.context["formset"].forms),
            len(self.collection.flyers.all()) + 1,
        )

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_non_group_members(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_member(self):
        self.client.force_login(self.member)
        data = {
            "catchment": CollectionCatchment.objects.first().id,
            "collector": Collector.objects.create(name="New Test Collector").id,
            "collection_system": CollectionSystem.objects.first().id,
            "waste_category": WasteCategory.objects.first().id,
            "connection_type": "VOLUNTARY",
            "allowed_materials": [
                self.allowed_material_1.id,
                self.allowed_material_2.id,
            ],
            "forbidden_materials": [
                self.forbidden_material_1.id,
                self.forbidden_material_2.id,
            ],
            "frequency": CollectionFrequency.objects.first().id,
            "valid_from": date(2022, 1, 1),
            "description": "This is a test case that should pass!",
            "form-INITIAL_FORMS": "0",
            "form-TOTAL_FORMS": "0",
        }
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.id}), data=data
        )
        self.assertEqual(response.status_code, 302)

    def test_post_creates_new_copy(self):
        self.client.force_login(self.member)
        self.assertEqual(Collection.objects.count(), 1)
        get_response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.pk})
        )
        initial = get_response.context["form"].initial
        data = {
            "catchment": initial["catchment"],
            "collector": initial["collector"],
            "collection_system": initial["collection_system"],
            "waste_category": initial["waste_category"],
            "connection_type": "VOLUNTARY",
            "allowed_materials": initial["allowed_materials"],
            "forbidden_materials": initial["forbidden_materials"],
            "frequency": initial["frequency"],
            "valid_from": initial["valid_from"],
            "description": initial["description"],
            "form-INITIAL_FORMS": "0",
            "form-TOTAL_FORMS": "0",
        }
        post_response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.pk}), data=data
        )
        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(Collection.objects.count(), 2)

    def test_post_copy_is_still_associated_with_unchanged_original_flyers(self):
        self.client.force_login(self.member)
        self.assertEqual(Collection.objects.count(), 1)
        get_response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.pk})
        )
        initial = get_response.context["form"].initial
        data = {
            "catchment": initial["catchment"],
            "collector": initial["collector"],
            "collection_system": initial["collection_system"],
            "waste_category": initial["waste_category"],
            "connection_type": "VOLUNTARY",
            "allowed_materials": initial["allowed_materials"],
            "forbidden_materials": initial["forbidden_materials"],
            "frequency": initial["frequency"],
            "valid_from": initial["valid_from"],
            "valid_until": "",
            "description": "This is the copy.",
            "form-INITIAL_FORMS": "1",
            "form-TOTAL_FORMS": "1",
            "form-0-url": self.flyer.url,
            "form-0-id": self.flyer.id,
        }
        self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.pk}), data=data
        )
        copy = Collection.objects.get(description="This is the copy.")
        self.assertEqual(copy.flyers.count(), 1)
        flyer = copy.flyers.first()
        self.assertEqual(flyer.url, self.flyer.url)


class CollectionCreateNewVersionViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_collection"
    url_name = "collection-new-version"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        MaterialCategory.objects.create(name="Biowaste component")
        cls.allowed_material_1 = WasteComponent.objects.create(
            name="Allowed material 1"
        )
        cls.allowed_material_2 = WasteComponent.objects.create(
            name="Allowed material 2"
        )
        cls.forbidden_material_1 = WasteComponent.objects.create(
            name="Forbidden material 1"
        )
        cls.forbidden_material_2 = WasteComponent.objects.create(
            name="Forbidden material 2"
        )
        waste_stream = WasteStream.objects.create(
            name="Test waste stream",
            category=WasteCategory.objects.create(name="Test category"),
        )
        waste_stream.allowed_materials.add(cls.allowed_material_1)
        waste_stream.allowed_materials.add(cls.allowed_material_2)
        waste_stream.forbidden_materials.add(cls.forbidden_material_1)
        waste_stream.forbidden_materials.add(cls.forbidden_material_2)
        with mute_signals(signals.post_save):
            cls.flyer = WasteFlyer.objects.create(
                abbreviation="WasteFlyer123", url="https://www.test-flyer.org"
            )
            cls.flyer2 = WasteFlyer.objects.create(
                abbreviation="WasteFlyer234", url="https://www.fest-flyer.org"
            )
        frequency = CollectionFrequency.objects.create(name="Test Frequency")
        cls.collection = Collection.objects.create(
            name="collection1",
            catchment=CollectionCatchment.objects.create(name="Test catchment"),
            collector=Collector.objects.create(name="Test collector"),
            collection_system=CollectionSystem.objects.create(name="Test system"),
            waste_stream=waste_stream,
            frequency=frequency,
            description="This is a test case.",
        )
        cls.collection.flyers.add(cls.flyer)
        cls.collection.flyers.add(cls.flyer2)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_non_group_members(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_group_members(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 200)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_non_group_members(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_member(self):
        self.client.force_login(self.member)
        data = {
            "catchment": CollectionCatchment.objects.first().id,
            "collector": Collector.objects.create(name="New Test Collector").id,
            "collection_system": CollectionSystem.objects.first().id,
            "waste_category": WasteCategory.objects.first().id,
            "connection_type": "VOLUNTARY",
            "allowed_materials": [
                self.allowed_material_1.id,
                self.allowed_material_2.id,
            ],
            "forbidden_materials": [
                self.forbidden_material_1.id,
                self.forbidden_material_2.id,
            ],
            "frequency": CollectionFrequency.objects.first().id,
            "valid_from": date(2022, 1, 1),
            "description": "This is a test case that should pass!",
            "form-INITIAL_FORMS": "0",
            "form-TOTAL_FORMS": "0",
        }
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.id}), data=data
        )
        self.assertEqual(response.status_code, 302)


# ----------- Collection utils -----------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CollectionAutocompleteViewTestCase(ViewWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Collection.objects.create(
            catchment=CollectionCatchment.objects.create(name="Hamburg")
        )
        Collection.objects.create(
            catchment=CollectionCatchment.objects.create(name="Berlin")
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse("collection-autocomplete"))
        self.assertEqual(response.status_code, 200)

    def test_get_returns_json_response(self):
        response = self.client.get(reverse("collection-autocomplete"))
        self.assertIsInstance(response, JsonResponse)

    def test_get_returns_only_collections_with_names_containing_filter_string(self):
        response = self.client.get(reverse("collection-autocomplete") + "?q=Ham")
        self.assertContains(response, "Hamburg")
        self.assertNotContains(response, "Berlin")


class CollectionAddPropertyValueViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_collectionpropertyvalue"
    url_name = "collection-add-property"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.collection = Collection.objects.create(name="Test Collection")
        cls.unit = Unit.objects.create(name="Test Unit")
        cls.prop = Property.objects.create(name="Test Property")
        cls.prop.allowed_units.add(cls.unit)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.collection.pk})
        )
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_get_initial_has_collection(self):
        request = RequestFactory().get(
            reverse(self.url_name, kwargs={"pk": self.collection.id})
        )
        view = views.CollectionAddPropertyValueView()
        view.setup(request)
        view.kwargs = {"pk": self.collection.id}
        initial = view.get_initial()
        expected = {
            "collection": self.collection.pk,
        }
        self.assertDictEqual(expected, initial)

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            "collection": self.collection.pk,
            "property": self.prop.pk,
            "unit": self.unit.pk,
            "year": 2022,
            "average": 123.5,
            "standard_deviation": 12.6,
        }
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.collection.pk}), data=data
        )
        self.assertEqual(response.status_code, 302)


class CollectionAddAggregatedPropertyValueViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "add_aggregatedcollectionpropertyvalue"
    url_name = "collectioncatchment-add-aggregatedpropertyvalue"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.catchment = CollectionCatchment.objects.create()
        Collection.objects.create(
            catchment=CollectionCatchment.objects.create(parent=cls.catchment)
        )
        Collection.objects.create(
            catchment=CollectionCatchment.objects.create(parent=cls.catchment)
        )
        cls.unit = Unit.objects.create(name="Test Unit")
        cls.prop = Property.objects.create(name="Test Property")
        cls.prop.allowed_units.add(cls.unit)

    def test_get_http_302_redirect_for_anonymous(self):
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.catchment.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_get_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.catchment.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.catchment.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_form_contains_exactly_one_submit_button(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse(self.url_name, kwargs={"pk": self.catchment.pk})
        )
        self.assertContains(response, 'type="submit"', count=1, status_code=200)

    def test_get_initial_has_collections(self):
        request = RequestFactory().get(
            reverse(self.url_name, kwargs={"pk": self.catchment.id})
        )
        view = views.CollectionCatchmentAddAggregatedPropertyView()
        view.setup(request)
        view.kwargs = {"pk": self.catchment.id}
        initial = view.get_initial()
        expected = {
            "collections": self.catchment.downstream_collections,
        }
        self.assertIn("collections", initial)
        self.assertQuerySetEqual(
            expected["collections"].order_by("id"),
            initial["collections"].order_by("id"),
        )

    def test_post_http_302_redirect_for_anonymous(self):
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.catchment.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_post_http_403_forbidden_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.catchment.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_post_http_302_redirect_for_members_with_minimal_data(self):
        self.client.force_login(self.member)
        data = {
            "collections": [
                collection.pk for collection in self.catchment.downstream_collections
            ],
            "property": self.prop.pk,
            "unit": self.unit.pk,
            "year": 2022,
            "average": 123.5,
            "standard_deviation": 12.6,
        }
        response = self.client.post(
            reverse(self.url_name, kwargs={"pk": self.catchment.pk}), data=data
        )
        self.assertEqual(response.status_code, 302)


class CollectionWasteSamplesViewTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    create_view = False
    public_list_view = False
    private_list_view = False
    detail_view = False
    delete_view = False

    model = Collection

    view_update_name = "collection-wastesamples"
    update_success_url_name = "collection-wastesamples"

    create_object_data = {"name": "Test Collection"}

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        material = Material.objects.create(name="Test Material")
        series = SampleSeries.objects.create(name="Test Series", material=material)
        cls.unpublished_object.samples.add(
            Sample.objects.create(
                name="Test Sample 1", material=material, series=series
            )
        )
        cls.sample = Sample.objects.create(
            name="Test Sample 2", material=material, series=series
        )

    def compile_update_post_data(self):
        data = {"sample": self.sample.pk, "submit": "Add"}
        return data

    def test_form_contains_one_submit_button_for_each_form(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_update_url(self.unpublished_object.pk))
        self.assertContains(response, 'type="submit"', count=2, status_code=200)
        self.assertContains(response, 'value="Add"')
        self.assertContains(response, 'value="Remove"')

    def test_unpublished_post_success_and_http_302_redirect_on_submit_of_add_form(self):
        self.client.force_login(self.owner_user)
        sample = Sample.objects.get(name="Test Sample 2")
        data = {"sample": sample.pk, "submit": "Add"}
        response = self.client.post(
            self.get_update_url(self.unpublished_object.pk), data, follow=True
        )
        self.assertRedirects(response, self.get_update_url(self.unpublished_object.pk))

    def test_unpublished_post_success_and_http_302_redirect_on_submit_of_remove_form(
        self,
    ):
        self.client.force_login(self.owner_user)
        sample = Sample.objects.get(name="Test Sample 1")
        data = {"sample": sample.pk, "submit": "Remove"}
        response = self.client.post(
            self.get_update_url(self.unpublished_object.pk), data, follow=True
        )
        self.assertRedirects(response, self.get_update_url(self.unpublished_object.pk))


class CollectionPredecessorsViewTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    create_view = False
    public_list_view = False
    private_list_view = False
    detail_view = False
    delete_view = False

    model = Collection

    view_update_name = "collection-predecessors"

    update_success_url_name = "collection-predecessors"

    create_object_data = {"name": "Test Collection"}
    update_object_data = {"name": "Test Collection"}

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.predecessor_collection = Collection.objects.create(
            name="Test Predecessor",
            catchment=cls.related_objects["catchment"],
            collector=cls.related_objects["collector"],
            collection_system=cls.related_objects["collection_system"],
            waste_stream=cls.related_objects["waste_stream"],
        )

    @classmethod
    def create_related_objects(cls):
        return {
            "catchment": CollectionCatchment.objects.create(name="Test Catchment"),
            "collector": Collector.objects.create(name="Test Collector"),
            "collection_system": CollectionSystem.objects.create(name="Test System"),
            "waste_stream": WasteStream.objects.create(
                name="Test Waste Stream",
                category=WasteCategory.objects.create(name="Test Category"),
            ),
        }

    def compile_update_post_data(self):
        # This is just for the standard access tests. Both forms function is tested separately in specific functions.
        return {"predecessor": self.predecessor_collection.pk, "submit": "Add"}

    def test_form_contains_one_submit_button_for_each_form(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(self.get_update_url(self.unpublished_object.pk))
        self.assertContains(response, 'type="submit"', count=2, status_code=200)
        self.assertContains(response, 'value="Add"')
        self.assertContains(response, 'value="Remove"')

    def test_post_success_and_http_302_redirect_on_submit_of_add_form(self):
        self.client.force_login(self.owner_user)
        data = {"predecessor": self.predecessor_collection.pk, "submit": "Add"}
        response = self.client.post(
            self.get_update_url(self.unpublished_object.pk), data=data, follow=True
        )
        self.assertRedirects(
            response, self.get_update_success_url(pk=self.unpublished_object.pk)
        )

    def test_post_success_and_http_302_redirect_on_submit_of_remove_form(self):
        self.client.force_login(self.owner_user)
        self.unpublished_object.add_predecessor(self.predecessor_collection)
        data = {"predecessor": self.predecessor_collection.pk, "submit": "Remove"}
        response = self.client.post(
            self.get_update_url(self.unpublished_object.pk), data=data, follow=True
        )
        self.assertRedirects(
            response, self.get_update_success_url(pk=self.unpublished_object.pk)
        )


class WasteCollectionMapViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = (
        "add_collection",
        "view_collection",
        "change_collection",
        "delete_collection",
    )
    url = reverse("WasteCollection")

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        style = MapLayerStyle.objects.create(name="default")
        layer = MapLayerConfiguration.objects.create(
            name="default", layer_type="features", style=style
        )
        map_config = MapConfiguration.objects.create(name="default")
        map_config.layers.add(layer)
        region = Region.objects.create(name="Test Region")
        cls.dataset, _ = GeoDataset.objects.get_or_create(
            model_name="WasteCollection",
            defaults={
                "name": "Waste Collections Europe",
                "description": "Waste Collection Systems of Europe",
                "region": region,
            },
        )
        cls.dataset.map_configuration = map_config
        cls.dataset.save()
        catchment = CollectionCatchment.objects.create(
            name="Test Catchment", region=region
        )
        cls.collection = Collection.objects.create(
            name="Test Collection", catchment=catchment
        )

    def test_http_200_ok_for_anonymous(self):
        response = self.client.get(self.url)
        redirect_url = (
            f'{reverse("WasteCollection")}?{urlencode({"valid_on": date.today()})}'
        )
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_http_200_ok_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        redirect_url = (
            f'{reverse("WasteCollection")}?{urlencode({"valid_on": date.today()})}'
        )
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )

    def test_uses_correct_template(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url, follow=True)
        redirect_url = f'{self.url}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertTemplateUsed(response, "waste_collection_map.html")

    def test_create_collection_option_visible_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url, follow=True)
        redirect_url = f'{self.url}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertContains(response, "Add new collection")

    def test_create_collection_option_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url, follow=True)
        redirect_url = f'{self.url}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertNotContains(response, "Add new collection")

    def test_copy_collection_option_visible_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url, follow=True)
        redirect_url = f'{self.url}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertContains(response, "Copy selected collection")

    def test_copy_collection_option_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url, follow=True)
        redirect_url = f'{self.url}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertNotContains(response, "Copy selected collection")

    def test_update_collection_option_visible_for_staff(self):
        self.client.force_login(self.staff)
        response = self.client.get(self.url, follow=True)
        redirect_url = f'{self.url}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertContains(response, "Edit selected collection")

    def test_update_collection_option_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url, follow=True)
        redirect_url = f'{self.url}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertNotContains(response, "Edit selected collection")

    def test_collection_dashboard_option_visible_for_member(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url, follow=True)
        redirect_url = f'{self.url}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertContains(response, "Waste collection explorer")

    def test_collection_dashboard_option_not_available_for_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url, follow=True)
        redirect_url = f'{self.url}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertContains(response, "Waste collection explorer")

    def test_range_slider_static_files_are_embedded(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url, follow=True)
        redirect_url = f'{self.url}?{urlencode({"valid_on": date.today()})}'
        self.assertRedirects(
            response, redirect_url, status_code=302, target_status_code=200
        )
        self.assertContains(response, "range_slider.min.js")
        self.assertContains(response, "range_slider.min.css")


from unittest.mock import patch


class WasteFlyerListCheckUrlsViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = "change_wasteflyer"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        with mute_signals(signals.post_save):
            for i in range(1, 5):
                WasteFlyer.objects.create(
                    title=f"Waste flyer {i}",
                    abbreviation=f"WF{i}",
                    url_valid=i % 2 == 0,
                )

    @patch("case_studies.soilcom.views.check_wasteflyer_urls.delay")
    def test_get_http_200_ok_for_members(self, mock_delay):
        mock_task = mock_delay.return_value
        mock_task.get.return_value = [[123]]  # Simulate callback_id as in view
        self.client.force_login(self.member)
        response = self.client.get(reverse("wasteflyer-list-check-urls"))
        self.assertEqual(response.status_code, 200)
        mock_delay.assert_called_once()

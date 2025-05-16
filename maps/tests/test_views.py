import json
from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import RequestFactory, TestCase
from django.urls import reverse

from maps.views import CatchmentCreateMergeLauView
from utils.tests.testcases import (
    AbstractTestCases,
    ViewSetWithPermissionsTestCase,
    ViewWithPermissionsTestCase,
)
from ..models import (
    Attribute,
    Catchment,
    GeoDataset,
    GeoPolygon,
    LauRegion,
    Location,
    MapConfiguration,
    MapLayerConfiguration,
    MapLayerStyle,
    NutsRegion,
    Region,
    RegionAttributeValue,
)
from ..views import MapMixin


class DummyBaseView:
    def get_context_data(self):
        return {}


class DummyMapView(MapMixin, DummyBaseView):
    pass


class MapMixinTestCase(TestCase):
    def setUp(self):
        default_layer_style = MapLayerStyle.objects.create(
            color="#000000",
            weight=1,
            opacity=1,
            fill_color="#000000",
        )
        layers = []
        for layer_type in ["region", "catchment", "features"]:
            layers.append(
                MapLayerConfiguration.objects.create(
                    name=f"The {layer_type} layer",
                    layer_type=layer_type,
                    load_layer=True,
                    feature_id="1",
                    api_basename=(
                        "api-catchment"
                        if layer_type == "features"
                        else f"api-{layer_type}"
                    ),
                    style=default_layer_style,
                )
            )
        self.map_config = MapConfiguration.objects.create(
            name="Test Map Configuration",
            adjust_bounds_to_layer="features",
            load_features_layer_summary=True,
        )
        self.map_config.layers.set(layers)
        self.factory = RequestFactory()
        self.view = DummyMapView()

    def mock_reverse_side_effect(name, *args, **kwargs):
        if "-detail" in name:
            return f"https://example.com/api/{name.split('-')[1]}/"
        else:
            return f"https://example.com/api/{name.split('-')[1]}/" + (
                f"{name.split('-')[2]}/" if len(name.split("-")) > 2 else ""
            )

    def test_get_map_title(self):
        self.view.map_title = "Test Title"
        self.assertEqual(self.view.get_map_title(), "Test Title")

    @patch("maps.views.MapMixin.get_region_feature_id")
    def test_override_load_region(self, mock_get_region_feature_id):
        mock_get_region_feature_id.return_value = 123
        request = self.factory.get("/?load_region=true")
        self.view.request = request
        map_config = self.view.get_context_data()["map_config"]
        self.assertTrue(map_config["loadRegion"])

        request = self.factory.get("/?load_region=false")
        self.view.request = request
        map_config = self.view.get_context_data()["map_config"]
        self.assertFalse(map_config["loadRegion"])

    @patch("maps.views.MapMixin.get_catchment_feature_id")
    def test_override_load_catchment(self, mock_get_catchment_feature_id):
        mock_get_catchment_feature_id.return_value = 123
        request = self.factory.get("/?load_catchment=true")
        self.view.request = request
        map_config = self.view.get_context_data()["map_config"]
        self.assertTrue(map_config["loadCatchment"])

        request = self.factory.get("/?load_catchment=false")
        self.view.request = request
        map_config = self.view.get_context_data()["map_config"]
        self.assertFalse(map_config["loadCatchment"])

    @patch("maps.views.MapMixin.get_features_geometries_url")
    def test_override_load_features(self, mock_get_features_geometries_url):
        mock_get_features_geometries_url.return_value = "features/"
        request = self.factory.get(
            f"/?load_features=true&map_config_id={self.map_config.id}"
        )
        self.view.request = request
        map_config = self.view.get_context_data()["map_config"]
        self.assertTrue(map_config["loadFeatures"])

        request = self.factory.get("/?load_features=false")
        self.view.request = request
        map_config = self.view.get_context_data()["map_config"]
        self.assertFalse(map_config["loadFeatures"])

    @patch("maps.views.reverse")
    def get_features_layer_details_url_template(self, mock_reverse):
        self.view.features_layer_details_url_template = "test-url"
        self.assertEqual(
            self.view.get_features_layer_details_url_template(), "test-url"
        )

        self.view.features_layer_details_url_template = None
        self.view.api_basename = "test-api"
        mock_reverse.return_value = "/mocked/url/0/"
        result = self.view.get_features_layer_details_url_template()
        mock_reverse.assert_called_once_with("test-api")
        self.assertEqual(result, "/mocked/url/")

    @patch("maps.views.reverse")
    def test_get_context_data(self, mock_reverse):
        request = self.factory.get(f"/?map_config_id={self.map_config.id}")
        self.view.request = request
        mock_reverse.return_value = "/mocked/url/0/"

        self.view.map_title = "Test title"
        context = self.view.get_context_data()
        map_config = context["map_config"]

        layer_style = {
            "color": "#000000",
            "weight": 1,
            "opacity": 1.0,
            "fillColor": "#000000",
            "fillOpacity": 0.2,
            "dashArray": "",
            "lineCap": "round",
            "lineJoin": "round",
            "fillRule": "evenodd",
            "className": "",
            "radius": 10.0,
        }

        self.assertEqual(context["map_title"], "Test title")
        self.assertEqual(map_config["regionId"], "1")
        self.assertEqual(
            map_config["regionLayerGeometriesUrl"], "/maps/api/region/geojson/"
        )
        self.assertTrue(map_config["loadRegion"])
        self.assertDictEqual(map_config["regionLayerStyle"], layer_style)
        self.assertEqual(map_config["loadCatchment"], True)
        self.assertEqual(
            map_config["catchmentLayerGeometriesUrl"], "/maps/api/catchment/geojson/"
        )
        self.assertEqual(map_config["catchmentId"], "1")
        self.assertDictEqual(map_config["catchmentLayerStyle"], layer_style)
        self.assertEqual(map_config["loadFeatures"], True)
        self.assertEqual(
            map_config["featuresLayerGeometriesUrl"], "/maps/api/catchment/geojson/"
        )
        self.assertEqual(map_config["applyFilterToFeatures"], False)
        self.assertDictEqual(map_config["featuresLayerStyle"], layer_style)
        self.assertEqual(map_config["adjustBoundsToLayer"], "features")
        self.assertEqual(map_config["featuresLayerSummariesUrl"], "")
        self.assertEqual(
            map_config["featuresLayerDetailsUrlTemplate"], "/maps/api/catchment/"
        )

    def test_layer_not_loaded_when_url_missing(self):
        for layer in self.map_config.layers.all():
            layer.load_layer = True
            layer.api_basename = ""
            layer.save()

        request = self.factory.get(f"/?map_config_id={self.map_config.id}")
        self.view.request = request
        self.view.map_title = "Test title"
        context = self.view.get_context_data()
        map_config = context["map_config"]

        self.assertEqual(map_config["regionLayerGeometriesUrl"], "")
        self.assertEqual(map_config["catchmentLayerGeometriesUrl"], "")
        self.assertEqual(map_config["featuresLayerGeometriesUrl"], "")
        self.assertFalse(map_config["loadRegion"])
        self.assertFalse(map_config["loadCatchment"])
        self.assertFalse(map_config["loadFeatures"])


# ----------- Location CRUD---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class LocationCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Location

    view_dashboard_name = "maps-dashboard"
    view_create_name = "location-create"
    view_published_list_name = "location-list"
    view_private_list_name = "location-list-owned"
    view_detail_name = "location-detail"
    view_update_name = "location-update"
    view_delete_name = "location-delete-modal"

    create_object_data = {
        "name": "Test Location",
        "address": "Test Address",
        "geom": Point(0, 0).wkt,
    }
    update_object_data = {
        "name": "Updated Test Location",
        "address": "Updated Test Address",
        "geom": Point(0, 0).wkt,
    }


# ----------- Region CRUD ----------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Region

    view_dashboard_name = "maps-dashboard"
    view_create_name = "region-create"
    view_published_list_name = "region-list"
    view_private_list_name = "region-list-owned"
    view_detail_name = "region-detail"
    view_update_name = "region-update"
    view_delete_name = "region-delete-modal"

    create_object_data = {
        "name": "Test Region",
        "country": "DE",
        "geom": "MULTIPOLYGON (((30 10, 40 40, 20 40, 10 20, 30 10)))",
    }
    update_object_data = {
        "name": "Updated Test Region",
        "country": "DE",
        "geom": "MULTIPOLYGON(((0 0, 0 100, 100 100, 100 0, 0 0)))",
    }


# ----------- Region Utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionMapViewTestCase(ViewWithPermissionsTestCase):
    member_permissions = ["add_region", "change_region"]
    url = reverse("region-map")

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region = Region.objects.create(name="Test Region")

    def test_get_http_302_redirect_to_login_for_anonymous(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{settings.LOGIN_URL}?next={self.url}")

    def test_get_http_200_ok_for_outsiders(self):
        self.client.force_login(self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_get_http_200_ok_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)

    def test_add_button_available_for_members(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url)
        self.assertContains(response, reverse("region-create"))


# ----------- Catchment CRUD--------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class CatchmentCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    model = Catchment

    view_dashboard_name = "maps-dashboard"
    view_create_name = "catchment-create"
    view_published_list_name = "catchment-list"
    view_private_list_name = "catchment-list-owned"
    view_detail_name = "catchment-detail"
    view_update_name = "catchment-update"
    view_delete_name = "catchment-delete-modal"

    create_object_data = {"name": "Test Catchment"}
    update_object_data = {"name": "Updated Test Catchment"}

    @classmethod
    def create_related_objects(cls):
        return {
            "region": Region.objects.create(name="Test Region"),
        }

    @classmethod
    def create_util_objects(cls):
        lau_1 = LauRegion.objects.create(
            name="Test Region 1",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((0, 0), (0, 2), (2, 2), (2, 0), (0, 0))))
            ),
        )
        lau_2 = LauRegion.objects.create(
            name="Test Region 2",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((0, 2), (0, 4), (2, 4), (2, 2), (0, 2))))
            ),
        )
        lau_3 = LauRegion.objects.create(
            name="Test Region 3",
            borders=GeoPolygon.objects.create(
                geom=MultiPolygon(Polygon(((1, 1), (1, 3), (3, 3), (3, 1), (1, 1))))
            ),
        )
        parent_region = Region.objects.create(name="Parent Region")
        return {
            "lau_region_1": lau_1.region_ptr,
            "lau_region_2": lau_2.region_ptr,
            "lau_region_3": lau_3.region_ptr,
            "parent_region": parent_region,
        }

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
            )  # This is the difference to the original test function
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
            )  # This is the difference to the original test function
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
            )  # This is the difference to the original test function
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
            )  # This is the difference to the original test function
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

    # -----------------------
    # CatchmentCreateSelectRegionView
    # -----------------------

    def test_create_select_region_view_get_as_anonymous(self):
        url = reverse("catchment-create-select-region")
        response = self.client.get(url)
        login_url = settings.LOGIN_URL
        expected_redirect = f"{login_url}?next={url}"
        self.assertRedirects(response, expected_redirect)

    def test_create_select_region_view_post_as_anonymous(self):
        url = reverse("catchment-create-select-region")
        response = self.client.post(url)
        login_url = settings.LOGIN_URL
        expected_redirect = f"{login_url}?next={url}"
        self.assertRedirects(response, expected_redirect)

    def test_create_select_region_view_get_as_authenticated_without_permission(self):
        self.client.force_login(self.non_owner_user)
        url = reverse("catchment-create-select-region")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, self.permission_denied_message, status_code=403)

    def test_create_select_region_view_post_as_authenticated_without_permission(self):
        self.client.force_login(self.non_owner_user)
        url = reverse("catchment-create-select-region")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, self.permission_denied_message, status_code=403)

    def test_create_select_region_view_get_as_authenticated_with_permission(self):
        self.client.force_login(self.user_with_add_perm)
        url = reverse("catchment-create-select-region")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_create_select_region_view_post_as_authenticated_with_permission(self):
        self.client.force_login(self.user_with_add_perm)
        url = reverse("catchment-create-select-region")
        data = self.create_object_data.copy()
        data.update(self.related_objects_post_data())
        initial_count = self.model.objects.count()
        response = self.client.post(url, data)
        self.assertEqual(self.model.objects.count(), initial_count + 1)
        new_object = self.model.objects.latest("pk")
        self.assertEqual(new_object.owner, self.user_with_add_perm)
        self.assertEqual(response.status_code, 302)

    def test_create_select_region_view_get_as_staff_user(self):
        self.client.force_login(self.staff_user)
        url = reverse("catchment-create-select-region")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_create_select_region_view_post_as_staff_user(self):
        self.client.force_login(self.staff_user)
        url = reverse("catchment-create-select-region")
        data = self.create_object_data.copy()
        data.update(self.related_objects_post_data())
        initial_count = self.model.objects.count()
        response = self.client.post(url, data)
        self.assertEqual(self.model.objects.count(), initial_count + 1)
        new_object = self.model.objects.latest("pk")
        self.assertEqual(new_object.owner, self.staff_user)
        self.assertEqual(response.status_code, 302)

    # -----------------------
    # CatchmentCreateDrawCustomView
    # -----------------------

    def test_create_draw_custom_view_get_as_anonymous(self):
        url = reverse("catchment-create-draw-custom")
        response = self.client.get(url)
        login_url = settings.LOGIN_URL
        expected_redirect = f"{login_url}?next={url}"
        self.assertRedirects(response, expected_redirect)

    def test_create_draw_custom_view_post_as_anonymous(self):
        url = reverse("catchment-create-draw-custom")
        response = self.client.post(url)
        login_url = settings.LOGIN_URL
        expected_redirect = f"{login_url}?next={url}"
        self.assertRedirects(response, expected_redirect)

    def test_create_draw_custom_view_get_as_authenticated_without_permission(self):
        self.client.force_login(self.non_owner_user)
        url = reverse("catchment-create-draw-custom")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, self.permission_denied_message, status_code=403)

    def test_create_draw_custom_view_post_as_authenticated_without_permission(self):
        self.client.force_login(self.non_owner_user)
        url = reverse("catchment-create-draw-custom")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, self.permission_denied_message, status_code=403)

    def test_create_draw_custom_view_get_as_authenticated_with_permission(self):
        self.client.force_login(self.user_with_add_perm)
        url = reverse("catchment-create-draw-custom")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_create_draw_custom_view_post_as_authenticated_with_permission(self):
        self.client.force_login(self.user_with_add_perm)
        url = reverse("catchment-create-draw-custom")
        data = {
            "name": "Newly created catchment",
            "geom": "MULTIPOLYGON (((30 10, 40 40, 20 40, 10 20, 30 10)))",
            "parent_region": self.util_objects["parent_region"].id,
        }
        initial_count = self.model.objects.count()
        response = self.client.post(url, data)
        self.assertEqual(self.model.objects.count(), initial_count + 1)
        new_object = self.model.objects.latest("pk")
        self.assertEqual(new_object.owner, self.user_with_add_perm)
        self.assertEqual(response.status_code, 302)

    def test_create_draw_custom_view_get_as_staff_user(self):
        self.client.force_login(self.staff_user)
        url = reverse("catchment-create-draw-custom")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_create_draw_custom_view_post_as_staff_user(self):
        self.client.force_login(self.staff_user)
        url = reverse("catchment-create-draw-custom")
        data = {
            "name": "Newly created catchment",
            "geom": "MULTIPOLYGON (((30 10, 40 40, 20 40, 10 20, 30 10)))",
            "parent_region": self.util_objects["parent_region"].id,
        }
        initial_count = self.model.objects.count()
        response = self.client.post(url, data)
        self.assertEqual(self.model.objects.count(), initial_count + 1)
        new_object = self.model.objects.latest("pk")
        self.assertEqual(new_object.owner, self.staff_user)
        self.assertEqual(response.status_code, 302)

    # -----------------------
    # CatchmentCreateMergeLauView
    # -----------------------

    def test_create_merge_lau_view_get_as_anonymous(self):
        url = reverse("catchment-create-merge-lau")
        response = self.client.get(url)
        login_url = settings.LOGIN_URL
        expected_redirect = f"{login_url}?next={url}"
        self.assertRedirects(response, expected_redirect)

    def test_create_merge_lau_view_post_as_anonymous(self):
        url = reverse("catchment-create-merge-lau")
        response = self.client.post(url)
        login_url = settings.LOGIN_URL
        expected_redirect = f"{login_url}?next={url}"
        self.assertRedirects(response, expected_redirect)

    def test_create_merge_lau_view_get_as_authenticated_without_permission(self):
        self.client.force_login(self.non_owner_user)
        url = reverse("catchment-create-merge-lau")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, self.permission_denied_message, status_code=403)

    def test_create_merge_lau_view_post_as_authenticated_without_permission(self):
        self.client.force_login(self.non_owner_user)
        url = reverse("catchment-create-merge-lau")
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, self.permission_denied_message, status_code=403)

    def test_create_merge_lau_view_get_as_authenticated_with_permission(self):
        self.client.force_login(self.user_with_add_perm)
        url = reverse("catchment-create-merge-lau")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_create_merge_lau_view_post_as_authenticated_with_permission(self):
        self.client.force_login(self.user_with_add_perm)
        url = reverse("catchment-create-merge-lau")
        data = {
            "name": "New Catchment Created By Merge",
            "parent_region": self.util_objects["parent_region"].pk,
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 3,
            "form-0-region": self.util_objects["lau_region_1"].pk,
            "form-1-region": self.util_objects["lau_region_2"].pk,
            "form-2-region": self.util_objects["lau_region_3"].pk,
        }
        initial_count = self.model.objects.count()
        response = self.client.post(url, data)
        self.assertEqual(self.model.objects.count(), initial_count + 1)
        new_object = self.model.objects.latest("pk")
        self.assertEqual(new_object.owner, self.user_with_add_perm)
        self.assertEqual(response.status_code, 302)

    def test_create_merge_lau_view_get_as_staff_user(self):
        self.client.force_login(self.staff_user)
        url = reverse("catchment-create-merge-lau")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_create_merge_lau_view_post_as_staff_user(self):
        self.client.force_login(self.staff_user)
        url = reverse("catchment-create-merge-lau")
        data = {
            "name": "New Catchment Created By Merge",
            "parent_region": self.util_objects["parent_region"].pk,
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 3,
            "form-0-region": self.util_objects["lau_region_1"].pk,
            "form-1-region": self.util_objects["lau_region_2"].pk,
            "form-2-region": self.util_objects["lau_region_3"].pk,
        }
        initial_count = self.model.objects.count()
        response = self.client.post(url, data, follow=True)
        self.assertEqual(self.model.objects.count(), initial_count + 1)
        new_object = self.model.objects.latest("pk")
        self.assertEqual(new_object.owner, self.staff_user)
        self.assertRedirects(
            response, reverse("catchment-detail", kwargs={"pk": new_object.pk})
        )

    def test_create_merge_lau_region_borders(self):
        url = reverse("catchment-create-merge-lau")
        data = {
            "name": "New Catchment Created By Merge",
            "parent_region": self.util_objects["parent_region"].pk,
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 3,
            "form-0-region": self.util_objects["lau_region_1"].pk,
            "form-1-region": self.util_objects["lau_region_2"].pk,
            "form-2-region": self.util_objects["lau_region_3"].pk,
        }
        request = RequestFactory().post(url, data)
        request.user = self.staff_user
        view = CatchmentCreateMergeLauView()
        view.setup(request)
        view.formset = view.get_formset()
        self.assertTrue(view.formset.is_valid())
        geom = MultiPolygon(
            Polygon(
                (
                    (0, 0),
                    (0, 2),
                    (0, 4),
                    (2, 4),
                    (2, 3),
                    (3, 3),
                    (3, 1),
                    (2, 1),
                    (2, 0),
                    (0, 0),
                )
            )
        )
        geom.normalize()
        self.assertTrue(view.create_region_borders().geom.equals_exact(geom))

    def test_get_region_name(self):
        url = reverse("catchment-create-merge-lau")
        data = {
            "name": "New Catchment Created By Merge",
            "parent_region": self.util_objects["parent_region"].pk,
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 2,
            "form-0-region": self.util_objects["lau_region_1"].pk,
            "form-1-region": self.util_objects["lau_region_2"].pk,
        }
        request = RequestFactory().post(url, data)
        request.user = self.staff_user
        view = CatchmentCreateMergeLauView()
        view.setup(request)
        form = view.get_form()
        self.assertTrue(form.is_valid())
        view.object = form.save()
        self.assertEqual("New Catchment Created By Merge", view.get_region_name())

    def test_get_region(self):
        url = reverse("catchment-create-merge-lau")
        data = {
            "name": "New Catchment Created By Merge",
            "parent_region": self.util_objects["parent_region"].pk,
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 3,
            "form-0-region": self.util_objects["lau_region_1"].pk,
            "form-1-region": self.util_objects["lau_region_2"].pk,
            "form-2-region": self.util_objects["lau_region_3"].pk,
        }
        request = RequestFactory().post(url, data)
        request.user = self.staff_user
        view = CatchmentCreateMergeLauView()
        view.setup(request)
        view.form = view.get_form()
        self.assertTrue(view.form.is_valid())
        view.object = view.form.save()
        view.formset = view.get_formset()
        self.assertTrue(view.formset.is_valid())
        geom = MultiPolygon(
            Polygon(
                (
                    (0, 0),
                    (0, 2),
                    (0, 4),
                    (2, 4),
                    (2, 3),
                    (3, 3),
                    (3, 1),
                    (2, 1),
                    (2, 0),
                    (0, 0),
                )
            )
        )
        geom.normalize()
        expected_region = Region.objects.create(
            name="New Catchment Created By Merge",
            borders=GeoPolygon.objects.create(geom=geom),
        )
        self.assertEqual(expected_region.name, view.get_region().name)
        self.assertTrue(view.get_region().borders.geom.equals_exact(geom))

    def test_catchment_with_correct_region_is_created_on_post_with_valid_data(self):
        url = reverse("catchment-create-merge-lau")
        self.client.force_login(self.staff_user)
        data = {
            "name": "New Catchment Created By Merge",
            "parent_region": self.util_objects["parent_region"].pk,
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 3,
            "form-0-region": self.util_objects["lau_region_1"].pk,
            "form-1-region": self.util_objects["lau_region_2"].pk,
            "form-2-region": self.util_objects["lau_region_3"].pk,
        }
        response = self.client.post(url, data, follow=True)
        catchment = Catchment.objects.get(name="New Catchment Created By Merge")
        self.assertRedirects(
            response, reverse("catchment-detail", kwargs={"pk": catchment.pk})
        )
        geom = MultiPolygon(
            Polygon(
                (
                    (0, 0),
                    (0, 2),
                    (0, 4),
                    (2, 4),
                    (2, 3),
                    (3, 3),
                    (3, 1),
                    (2, 1),
                    (2, 0),
                    (0, 0),
                )
            )
        )
        geom.normalize()
        expected_region = Region.objects.create(
            name="New Catchment Created By Merge",
            borders=GeoPolygon.objects.create(geom=geom),
        )
        self.assertEqual(expected_region.name, catchment.region.name)
        self.assertTrue(catchment.region.borders.geom.equals_exact(geom))
        self.assertTrue(catchment.type == "custom")
        self.assertEqual(catchment.parent_region, self.util_objects["parent_region"])

    def test_at_least_one_entry_in_formset_is_enforced(self):
        url = reverse("catchment-create-merge-lau")
        self.client.force_login(self.staff_user)
        data = {
            "name": "New Catchment Created By Merge",
            "parent_region": self.util_objects["parent_region"].pk,
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 2,
            "form-0-region": "",
            "form-1-region": "",
        }
        response = self.client.post(url, data)
        self.assertEqual(200, response.status_code)
        self.assertIn(
            "You must select at least one region.",
            response.context["formset"].non_form_errors(),
        )

    def test_empty_forms_are_ignored(self):
        url = reverse("catchment-create-merge-lau")
        self.client.force_login(self.staff_user)
        data = {
            "name": "New Catchment Created By Merge",
            "parent_region": self.util_objects["parent_region"].pk,
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 4,
            "form-0-region": self.util_objects["lau_region_1"].pk,
            "form-1-region": self.util_objects["lau_region_2"].pk,
            "form-2-region": "",
            "form-3-region": "",
        }
        response = self.client.post(url, data)
        self.assertEqual(302, response.status_code)


# ----------- Catchment API---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class NutsRegionMapViewTestCase(ViewWithPermissionsTestCase):

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
        GeoDataset.objects.create(
            name="Test Dataset",
            region=region,
            model_name="NutsRegion",
            map_configuration=map_config,
        )

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(reverse("NutsRegion"))
        self.assertEqual(response.status_code, 200)


class NutsAndLauCatchmentPedigreeAPITestCase(ViewSetWithPermissionsTestCase):
    member_permissions = "add_collection"

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        level_0_region = NutsRegion.objects.create(
            nuts_id="XX", levl_code=0, name_latn="Level 0 Region"
        )
        cls.level_0_catchment = Catchment.objects.create(
            region=level_0_region.region_ptr
        )
        level_1_region = NutsRegion.objects.create(
            nuts_id="XX0",
            levl_code=1,
            name_latn="Level 1 Region",
            parent=level_0_region,
        )
        cls.level_1_catchment = Catchment.objects.create(
            region=level_1_region.region_ptr, parent_region=level_0_region.region_ptr
        )
        level_2_region_1 = NutsRegion.objects.create(
            nuts_id="XX00",
            levl_code=2,
            name_latn="Level 2 Region 1",
            parent=level_1_region,
        )
        cls.level_2_catchment_1 = Catchment.objects.create(
            region=level_2_region_1.region_ptr, parent_region=level_1_region.region_ptr
        )
        level_2_region_2 = NutsRegion.objects.create(
            nuts_id="XX01",
            levl_code=2,
            name_latn="Level 2 Region 2",
            parent=level_1_region,
        )
        cls.level_2_catchment_1 = Catchment.objects.create(
            region=level_2_region_2.region_ptr, parent_region=level_1_region.region_ptr
        )
        level_3_region_1 = NutsRegion.objects.create(
            nuts_id="XX000",
            levl_code=3,
            name_latn="Level 3 Region 1",
            parent=level_2_region_1,
        )
        cls.level_3_catchment_1 = Catchment.objects.create(
            region=level_3_region_1.region_ptr,
            parent_region=level_2_region_1.region_ptr,
        )
        level_3_region_2 = NutsRegion.objects.create(
            nuts_id="XX011",
            levl_code=3,
            name_latn="Level 3 Region 2",
            parent=level_2_region_2,
        )
        cls.level_3_catchment_2 = Catchment.objects.create(
            region=level_3_region_2.region_ptr,
            parent_region=level_2_region_2.region_ptr,
        )
        level_4_region_1 = LauRegion.objects.create(
            lau_id="X00000000",
            lau_name="Level 4 Region 1",
            nuts_parent=level_3_region_1,
        )
        cls.level_4_catchment_1 = Catchment.objects.create(
            region=level_4_region_1.region_ptr,
            parent_region=level_3_region_1.region_ptr,
        )
        level_4_region_2 = LauRegion.objects.create(
            lau_id="X00000001",
            lau_name="Level 4 Region 2",
            nuts_parent=level_3_region_2,
        )
        cls.level_4_catchment_2 = Catchment.objects.create(
            region=level_4_region_2.region_ptr,
            parent_region=level_3_region_2.region_ptr,
        )

    def test_get_http_200_ok_for_anonymous(self):
        catchment = Catchment.objects.get(region__nutsregion__nuts_id="XX")
        response = self.client.get(
            reverse("data.nuts_lau_catchment_options"),
            {"id": catchment.id, "direction": "children"},
        )
        self.assertEqual(response.status_code, 200)

    def test_get_http_400_bad_request_on_missing_query_parameter_id(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("data.nuts_lau_catchment_options"), {"direction": "children"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            'Query parameter "id" missing. Must provide valid catchment id.',
        )

    def test_get_http_400_bad_request_on_missing_query_parameter_direction(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("data.nuts_lau_catchment_options"),
            {"id": self.level_0_catchment.id},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            'Missing or wrong query parameter "direction". Options: "parents", "children"',
        )

    def test_get_http_400_bad_request_on_wrong_query_parameter_direction(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("data.nuts_lau_catchment_options"),
            {"id": self.level_0_catchment.id, "direction": "south"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            'Missing or wrong query parameter "direction". Options: "parents", "children"',
        )

    def test_get_http_404_bad_request_on_non_existing_region_id(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("data.nuts_lau_catchment_options"),
            {"id": 0, "direction": "parents"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data["detail"],
            "A NUTS region with the provided id does not exist.",
        )

    def test_get_response_contains_level_4_in_children_if_input_is_level_3(self):
        self.client.force_login(self.outsider)
        response = self.client.get(
            reverse("data.nuts_lau_catchment_options"),
            {"id": self.level_3_catchment_1.id, "direction": "children"},
        )
        self.assertIn("id_level_4", response.data)


class NutsRegionSummaryAPIViewTestCase(ViewSetWithPermissionsTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        NutsRegion.objects.create(nuts_id="TE57", name_latn="Test NUTS")

    def setUp(self):
        self.region = NutsRegion.objects.get(nuts_id="TE57")

    def test_get_http_200_ok_for_anonymous(self):
        response = self.client.get(
            reverse("data.nutsregion-summary"), {"id": self.region.pk}
        )
        self.assertEqual(response.status_code, 200)

    def test_returns_correct_data(self):
        response = self.client.get(
            reverse("data.nutsregion-summary"), {"id": self.region.pk}
        )
        self.assertIn("summaries", response.data)
        self.assertEqual(response.data["summaries"][0]["Name"], self.region.name_latn)


# ----------- Attribute CRUD -------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class AttributeCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True

    model = Attribute

    view_dashboard_name = "maps-dashboard"
    view_create_name = "attribute-create"
    view_modal_create_name = "attribute-create-modal"
    view_published_list_name = "attribute-list"
    view_private_list_name = "attribute-list-owned"
    view_detail_name = "attribute-detail"
    view_modal_detail_name = "attribute-detail-modal"
    view_update_name = "attribute-update"
    view_modal_update_name = "attribute-update-modal"
    view_delete_name = "attribute-delete-modal"

    create_object_data = {
        "name": "Test Attribute",
        "unit": "Test Unit",
    }
    update_object_data = {
        "name": "Updated Test Attribute",
        "unit": "Updated Test Unit",
        "description": "Updated description",
    }


# ----------- Region Attribute Value CRUD ------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionAttributeValueCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True
    public_list_view = False
    private_list_view = False

    model = RegionAttributeValue

    view_dashboard_name = "maps-dashboard"
    view_create_name = "regionattributevalue-create"
    view_modal_create_name = "regionattributevalue-create-modal"
    view_detail_name = "regionattributevalue-detail"
    view_modal_detail_name = "regionattributevalue-detail-modal"
    view_update_name = "regionattributevalue-update"
    view_modal_update_name = "regionattributevalue-update-modal"
    view_delete_name = "regionattributevalue-delete-modal"

    create_object_data = {"name": "Test Value", "value": 123.321, "date": date.today()}
    update_object_data = {
        "name": "Updated Test Value",
        "value": 456.654,
        "date": date.today(),
    }

    @classmethod
    def create_related_objects(cls):
        return {
            "region": Region.objects.create(owner=cls.owner_user, name="Test Region"),
            "attribute": Attribute.objects.create(
                name="Test Attribute", unit="Test Unit"
            ),
        }

    def get_update_success_url(self, pk=None):
        return reverse(
            "region-detail", kwargs={"pk": self.related_objects["region"].pk}
        )

    def get_delete_success_url(self, publication_status=None):
        return reverse(
            "region-detail", kwargs={"pk": self.related_objects["region"].pk}
        )


# ----------- Region Utils ---------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------


class RegionOfLauAutocompleteViewTestCase(ViewWithPermissionsTestCase):
    url = reverse("region-of-lau-autocomplete")

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.region_1 = LauRegion.objects.create(
            name="Test Region 1", lau_id="123"
        ).region_ptr
        cls.region_2 = LauRegion.objects.create(
            name="Test Region 2", lau_id="234"
        ).region_ptr
        cls.region_3 = Region.objects.create(name="Test Region Not In Queryset")

    def test_all_lau_regions_with_matching_name_string_in_queryset(self):
        response = self.client.get(self.url, data={"q": "Test"})
        self.assertEqual(200, response.status_code)
        ids = [region["id"] for region in json.loads(response.content)["results"]]
        self.assertListEqual([str(lau.id) for lau in LauRegion.objects.all()], ids)

    def test_all_lau_region_with_matching_lau_id_in_queryset(self):
        response = self.client.get(self.url, data={"q": "12"})
        self.assertEqual(200, response.status_code)
        ids = [region["id"] for region in json.loads(response.content)["results"]]
        self.assertListEqual(
            [str(lau.id) for lau in LauRegion.objects.filter(lau_id="123")], ids
        )

    def test_all_lau_region_with_matching_lau_id_in_queryset_2(self):
        response = self.client.get(self.url, data={"q": "23"})
        self.assertEqual(200, response.status_code)
        ids = [region["id"] for region in json.loads(response.content)["results"]]
        self.assertListEqual([str(lau.id) for lau in LauRegion.objects.all()], ids)


class ClearGeojsonCacheViewTest(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(username="staff", password="pass")
        self.staff_user.is_staff = True
        self.staff_user.save()

        self.non_staff_user = User.objects.create_user(
            username="nonstaff", password="pass"
        )

    @patch("maps.views.clear_geojson_cache_pattern")
    def test_clear_geojson_cache_as_staff(self, mock_clear):
        self.client.login(username="staff", password="pass")
        url = reverse("clear-geojson-cache") + "?pattern=testpattern"
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "success", "message": "Cache cleared with pattern: testpattern"},
        )

        mock_clear.assert_called_once_with("testpattern")

    def test_clear_geojson_cache_as_non_staff(self):
        self.client.login(username="nonstaff", password="pass")
        url = reverse("clear-geojson-cache")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)

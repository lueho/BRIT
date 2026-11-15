from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import path
from django_filters import FilterSet, ModelChoiceFilter
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from sources.waste_collection.models import Collection
from utils.object_management import checks

urlpatterns = []


class UncoveredCollectionView(APIView):
    model = Collection


class ExemptCollectionView(APIView):
    model = Collection
    policy_exempt = "Reference endpoint intentionally lists published collections."


class PublicAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]


class PolicyRouteCoverageTests(SimpleTestCase):
    def run_route_check(self, view_class):
        patterns = [path("synthetic/", view_class.as_view())]
        with (
            patch(f"{__name__}.urlpatterns", patterns),
            override_settings(ROOT_URLCONF=__name__),
        ):
            return checks.policy_route_coverage_check(None)

    def test_governed_route_without_policy_adapter_reports_e020(self):
        errors = self.run_route_check(UncoveredCollectionView)

        self.assertTrue(any(error.id == "object_management.E020" for error in errors))
        self.assertTrue(any("synthetic/" in error.msg for error in errors))
        self.assertTrue(
            any("waste_collection.collection" in error.msg for error in errors)
        )

    def test_reasoned_policy_exemption_covers_governed_route(self):
        errors = self.run_route_check(ExemptCollectionView)

        self.assertFalse(any(error.id == "object_management.E020" for error in errors))

    def test_empty_policy_exemption_does_not_cover_governed_route(self):
        class EmptyExemptionView(UncoveredCollectionView):
            policy_exempt = ""

        errors = self.run_route_check(EmptyExemptionView)

        self.assertTrue(any(error.id == "object_management.E020" for error in errors))

    def test_public_api_without_governed_model_reports_e021(self):
        errors = self.run_route_check(PublicAPIView)

        self.assertTrue(any(error.id == "object_management.E021" for error in errors))

    def test_governed_reference_filter_outside_base_reports_e022(self):
        class UncoveredReferenceFilterSet(FilterSet):
            collection = ModelChoiceFilter(queryset=Collection.objects.all())

            class Meta:
                model = Collection
                fields = ()

        with patch.object(
            UncoveredReferenceFilterSet,
            "reference_choices_policy_exempt",
            "",
            create=True,
        ):
            errors = checks.policy_route_coverage_check(None)

        self.assertTrue(any(error.id == "object_management.E022" for error in errors))
        self.assertTrue(
            any(
                "UncoveredReferenceFilterSet" in error.msg
                for error in errors
                if error.id == "object_management.E022"
            )
        )

from unittest.mock import patch

from django import forms
from django.test import SimpleTestCase, override_settings
from django.urls import path
from django_filters import FilterSet, ModelChoiceFilter
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from sources.waste_collection.models import Collection
from utils.filters import PolicyScopedChoicesMixin
from utils.forms import UserCreatedObjectFormMixin
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


class ThirdPartyAPIView(APIView):
    __module__ = "third_party.api.views"
    authentication_classes = []
    permission_classes = [AllowAny]


class UnscopedChoiceForm(forms.Form):
    collection = forms.ModelChoiceField(queryset=Collection.objects.all())


class ScopedChoiceForm(UserCreatedObjectFormMixin, forms.Form):
    collection = forms.ModelChoiceField(queryset=Collection.objects.all())


class PolicyRouteCoverageTests(SimpleTestCase):
    def run_route_check(self, view_class=None):
        patterns = [path("synthetic/", view_class.as_view())] if view_class else []
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

    def test_public_api_outside_project_packages_does_not_report_e021(self):
        errors = self.run_route_check(ThirdPartyAPIView)

        self.assertFalse(any(error.id == "object_management.E021" for error in errors))

    def test_obtain_auth_token_is_not_a_project_e021_finding(self):
        errors = self.run_route_check(ObtainAuthToken)

        self.assertFalse(any(error.id == "object_management.E021" for error in errors))

    def test_governed_choice_form_without_policy_mixin_reports_e023(self):
        class UncoveredChoiceView(APIView):
            form_class = UnscopedChoiceForm

        errors = self.run_route_check(UncoveredChoiceView)

        self.assertTrue(any(error.id == "object_management.E023" for error in errors))

    def test_governed_choice_form_with_policy_mixin_is_covered(self):
        class CoveredChoiceView(APIView):
            form_class = ScopedChoiceForm

        errors = self.run_route_check(CoveredChoiceView)

        self.assertFalse(any(error.id == "object_management.E023" for error in errors))

    def test_governed_choice_form_with_reasoned_exemption_is_covered(self):
        class ExemptChoiceView(APIView):
            form_class = UnscopedChoiceForm
            reference_choices_policy_exempt = (
                "Choices are filtered by a dedicated policy-aware adapter."
            )

        errors = self.run_route_check(ExemptChoiceView)

        self.assertFalse(any(error.id == "object_management.E023" for error in errors))

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
            errors = self.run_route_check()

        self.assertTrue(any(error.id == "object_management.E022" for error in errors))
        self.assertTrue(
            any(
                "UncoveredReferenceFilterSet" in error.msg
                for error in errors
                if error.id == "object_management.E022"
            )
        )

    def test_governed_reference_filter_with_policy_mixin_is_covered(self):
        class ScopedReferenceFilterSet(PolicyScopedChoicesMixin, FilterSet):
            collection = ModelChoiceFilter(queryset=Collection.objects.all())

            class Meta:
                model = Collection
                fields = ()

        errors = self.run_route_check()

        self.assertFalse(
            any(
                error.id == "object_management.E022"
                and "ScopedReferenceFilterSet" in error.msg
                for error in errors
            )
        )

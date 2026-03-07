from django.contrib.auth.models import AnonymousUser, User
from django.test import TestCase

from bibliography.models import Source

from ..filters import CatchmentFilterSet, GeoDataSetFilterSet
from ..models import Catchment, GeoDataset, Region


class CatchmentFilterTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catchment_1 = Catchment.objects.create(name="Catchment 1")

    def test_filter_valid_on_valid_input(self):
        data = {"name": "Catchment"}
        filtr = CatchmentFilterSet(data, queryset=Catchment.objects.all())
        form = filtr.form
        self.assertTrue(form.is_valid())
        self.assertQuerySetEqual(Catchment.objects.all(), filtr.qs)

    def test_filter_form_has_no_formtags(self):
        filtr = CatchmentFilterSet(queryset=Catchment.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)


class GeoDataSetFilterTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create(username="owner")
        cls.region = Region.objects.create(
            name="Hamburg",
            country="DE",
            owner=cls.owner,
            publication_status="published",
        )
        cls.other_region = Region.objects.create(
            name="Nantes",
            country="FR",
            owner=cls.owner,
            publication_status="published",
        )
        cls.source = Source.objects.create(
            title="Tree inventory",
            owner=cls.owner,
            publication_status="published",
        )
        cls.other_source = Source.objects.create(
            title="Greenhouse inventory",
            owner=cls.owner,
            publication_status="published",
        )
        cls.matching_dataset = GeoDataset.objects.create(
            name="Hamburg Tree Dataset",
            owner=cls.owner,
            publication_status="published",
            region=cls.region,
            model_name="NutsRegion",
        )
        cls.matching_dataset.sources.add(cls.source)
        cls.other_dataset = GeoDataset.objects.create(
            name="Nantes Greenhouse Dataset",
            owner=cls.owner,
            publication_status="published",
            region=cls.other_region,
            model_name="NantesGreenhouses",
        )
        cls.other_dataset.sources.add(cls.other_source)

    def test_filter_valid_on_region_source_and_type(self):
        class RequestLike:
            user = AnonymousUser()

        filtr = GeoDataSetFilterSet(
            data={
                "scope": "published",
                "name": "Tree",
                "model_name": "NutsRegion",
                "region": str(self.region.pk),
                "source": str(self.source.pk),
            },
            queryset=GeoDataset.objects.all(),
            request=RequestLike(),
        )
        self.assertTrue(filtr.form.is_valid())
        self.assertQuerySetEqual(
            filtr.qs.order_by("pk"),
            [self.matching_dataset],
            transform=lambda obj: obj,
        )

    def test_filter_form_has_no_formtags(self):
        filtr = GeoDataSetFilterSet(queryset=GeoDataset.objects.all())
        self.assertFalse(filtr.form.helper.form_tag)

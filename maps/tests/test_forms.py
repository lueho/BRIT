from django.contrib.gis.geos import MultiPolygon, Polygon
from django.forms import formset_factory
from django.test import TestCase

from ..forms import RegionMergeForm, RegionMergeFormSet, RegionModelForm
from ..models import LauRegion, Region


class RegionModelFormTestCase(TestCase):
    def test_valid_form_submission(self):
        poly = MultiPolygon(Polygon(((0, 0), (1, 1), (1, 0), (0, 0))))

        form_data = {
            "name": "Test Region",
            "country": "TE",
            "description": "Test Description",
            "geom": poly,
        }

        form = RegionModelForm(data=form_data)

        self.assertTrue(form.is_valid())

        region = form.save()
        self.assertIsNotNone(region.pk)
        self.assertIsNotNone(region.borders.pk)
        self.assertEqual(region.borders.geom, poly)

    def test_invalid_form_submission(self):
        form_data = {
            "name": "Test Region",
            # 'country' is required but missing
            "description": "Test Description",
            "geom": "invalid_geometry",
        }

        form = RegionModelForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("country", form.errors)
        self.assertIn("geom", form.errors)

    def test_save_method_with_commit_false(self):
        poly = MultiPolygon(Polygon(((0, 0), (1, 1), (1, 0), (0, 0))))

        form_data = {
            "name": "Test Region Without Commit",
            "country": "Test Country",
            "description": "Test Description",
            "geom": poly,
        }

        form = RegionModelForm(data=form_data)
        self.assertTrue(form.is_valid())

        region = form.save(commit=False)

        self.assertIsNone(region.pk)

        region.save()
        self.assertIsNotNone(region.pk)
        self.assertIsNotNone(region.borders.pk)
        self.assertEqual(region.borders.geom, poly)

    def test_edit_form_prepopulates_geom_initial(self):
        poly = MultiPolygon(Polygon(((0, 0), (1, 1), (1, 0), (0, 0))))
        region = Region.objects.create(
            name="Existing Region",
            country="DE",
            borders=Region._meta.get_field("borders").related_model.objects.create(
                geom=poly
            ),
        )

        form = RegionModelForm(instance=region)

        self.assertIn("geom", form.initial)
        self.assertEqual(form.initial["geom"], poly)

    def test_save_updates_existing_region_geometry(self):
        original_poly = MultiPolygon(Polygon(((0, 0), (1, 1), (1, 0), (0, 0))))
        updated_poly = MultiPolygon(Polygon(((0, 0), (2, 2), (2, 0), (0, 0))))
        region = Region.objects.create(
            name="Existing Region",
            country="DE",
            borders=Region._meta.get_field("borders").related_model.objects.create(
                geom=original_poly
            ),
        )
        original_borders_pk = region.borders_id

        form = RegionModelForm(
            data={
                "name": region.name,
                "country": region.country,
                "description": region.description,
                "geom": updated_poly,
            },
            instance=region,
        )

        self.assertTrue(form.is_valid(), form.errors)
        updated_region = form.save()

        self.assertEqual(updated_region.borders_id, original_borders_pk)
        self.assertEqual(updated_region.borders.geom, updated_poly)


class TestRegionMergeFormset(TestCase):
    @classmethod
    def setUpTestData(cls):
        lau = LauRegion.objects.create(
            name="Test Region 1", publication_status="published"
        )
        cls.region_1 = lau.region_ptr
        lau = LauRegion.objects.create(
            name="Test Region 2", publication_status="published"
        )
        cls.region_2 = lau.region_ptr
        cls.region_3 = Region.objects.create(
            name="Not In Queryset", publication_status="published"
        )

    def test_formset_has_lauregions_as_queryset(self):
        data = {
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 2,
            "form-0-region": self.region_1,
            "form-1-region": self.region_2,
        }
        FormSet = formset_factory(RegionMergeForm, formset=RegionMergeFormSet)
        formset = FormSet(data)
        for form in formset:
            self.assertIn(self.region_1, form.fields["region"].queryset)
            self.assertIn(self.region_2, form.fields["region"].queryset)
            self.assertNotIn(self.region_3, form.fields["region"].queryset)

    def test_validated_with_valid_data(self):
        data = {
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 2,
            "form-0-region": self.region_1,
            "form-1-region": self.region_2,
        }
        FormSet = formset_factory(RegionMergeForm, formset=RegionMergeFormSet)
        formset = FormSet(data)
        self.assertTrue(formset.is_valid())

    def test_clean_enforces_at_least_one_valid_region(self):
        data = {
            "form-INITIAL_FORMS": 2,
            "form-TOTAL_FORMS": 2,
            "form-0-region": "",
            "form-1-region": "",
        }
        FormSet = formset_factory(RegionMergeForm, formset=RegionMergeFormSet)
        formset = FormSet(data)
        self.assertFalse(formset.is_valid())
        self.assertIn("You must select at least one region.", formset.non_form_errors())

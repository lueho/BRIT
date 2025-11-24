from datetime import date

from django.db.models import signals
from django.forms import formset_factory
from django.http import QueryDict
from django.test import TestCase
from factory.django import mute_signals

from distributions.models import TemporalDistribution, Timestep
from materials.models import Material, MaterialCategory, Sample, SampleSeries

from ..forms import (
    CollectionAddPredecessorForm,
    CollectionAddWasteSampleForm,
    CollectionModelForm,
    CollectionRemovePredecessorForm,
    CollectionRemoveWasteSampleForm,
    CollectionSeasonForm,
    CollectionSeasonFormSet,
    WasteFlyerFormSet,
    WasteFlyerModelForm,
)
from ..models import (
    Collection,
    CollectionCatchment,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionSeason,
    CollectionSystem,
    Collector,
    WasteCategory,
    WasteComponent,
    WasteFlyer,
    WasteStream,
)


def dict_to_querydict(data):
    """
    Convert a dict to QueryDict for form testing.
    Handles list values properly (multiple values for same key).
    """
    qd = QueryDict(mutable=True)
    for key, value in data.items():
        if isinstance(value, list):
            qd.setlist(key, value)
        else:
            qd[key] = value
    return qd


class CollectionSeasonModelFormTestCase(TestCase):
    def test_passing_values_other_than_from_distribution_months_of_the_year_raises_validation_errors(
        self,
    ):
        data = {
            "distribution": TemporalDistribution.objects.default(),
            "first_timestep": Timestep.objects.default(),
            "last_timestep": Timestep.objects.default(),
        }
        form = CollectionSeasonForm(data)
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["distribution"],
            ["Select a valid choice. That choice is not one of the available choices."],
        )
        self.assertEqual(
            form.errors["first_timestep"],
            ["Select a valid choice. That choice is not one of the available choices."],
        )
        self.assertEqual(
            form.errors["last_timestep"],
            ["Select a valid choice. That choice is not one of the available choices."],
        )


class CollectionSeasonFormSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.distribution = TemporalDistribution.objects.get(name="Months of the year")
        cls.january = Timestep.objects.get(name="January")
        cls.february = Timestep.objects.get(name="February")
        cls.march = Timestep.objects.get(name="March")
        cls.april = Timestep.objects.get(name="April")
        cls.december = Timestep.objects.get(name="December")
        cls.whole_year, _ = CollectionSeason.objects.get_or_create(
            distribution=cls.distribution,
            first_timestep=cls.january,
            last_timestep=cls.december,
        )

    def test_formset_creates_new_seasons_if_not_existing(self):
        with self.assertRaises(CollectionSeason.DoesNotExist):
            CollectionSeason.objects.get(
                distribution=self.distribution,
                first_timestep=self.january,
                last_timestep=self.march,
            )
        data = {
            "form-INITIAL_FORMS": 1,
            "form-TOTAL_FORMS": 2,
            "form-0-distribution": self.distribution,
            "form-0-first_timestep": self.january,
            "form-0-last_timestep": self.march,
            "form-1-distribution": self.distribution,
            "form-1-first_timestep": self.april,
            "form-1-last_timestep": self.december,
        }
        FormSet = formset_factory(CollectionSeasonForm, formset=CollectionSeasonFormSet)
        frequency = CollectionFrequency.objects.create(
            name="Test Frequency", type="Fixed"
        )
        formset = FormSet(data, parent_object=frequency, relation_field_name="seasons")
        self.assertTrue(formset.is_valid())
        formset.save()
        CollectionSeason.objects.get(
            distribution=self.distribution,
            first_timestep=self.january,
            last_timestep=self.march,
        )
        CollectionSeason.objects.get(
            distribution=self.distribution,
            first_timestep=self.april,
            last_timestep=self.december,
        )

    def test_formset_does_not_change_existing_seasons(self):
        data = {
            "form-INITIAL_FORMS": 1,
            "form-TOTAL_FORMS": 2,
            "form-0-distribution": self.distribution,
            "form-0-first_timestep": self.january,
            "form-0-last_timestep": self.march,
            "form-1-distribution": self.distribution,
            "form-1-first_timestep": self.april,
            "form-1-last_timestep": self.december,
        }
        FormSet = formset_factory(CollectionSeasonForm, formset=CollectionSeasonFormSet)
        frequency = CollectionFrequency.objects.create(
            name="Test Frequency", type="Fixed"
        )
        formset = FormSet(data, parent_object=frequency, relation_field_name="seasons")
        self.assertTrue(formset.is_valid())
        formset.save()
        self.assertEqual(self.distribution, self.whole_year.distribution)
        self.assertEqual(self.january, self.whole_year.first_timestep)
        self.assertEqual(self.december, self.whole_year.last_timestep)

    def test_seasons_cannot_overlap(self):
        data = {
            "form-INITIAL_FORMS": 1,
            "form-TOTAL_FORMS": 2,
            "form-0-distribution": self.distribution,
            "form-0-first_timestep": self.january,
            "form-0-last_timestep": self.march,
            "form-1-distribution": self.distribution,
            "form-1-first_timestep": self.february,
            "form-1-last_timestep": self.april,
        }
        FormSet = formset_factory(CollectionSeasonForm, formset=CollectionSeasonFormSet)
        formset = FormSet(data, relation_field_name="seasons")
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset.non_form_errors()[0],
            "The seasons must not overlap and must be given in order.",
        )

    def test_seasons_cannot_overlap_2(self):
        data = {
            "form-INITIAL_FORMS": 1,
            "form-TOTAL_FORMS": 2,
            "form-0-distribution": self.distribution,
            "form-0-first_timestep": self.february,
            "form-0-last_timestep": self.april,
            "form-1-distribution": self.distribution,
            "form-1-first_timestep": self.january,
            "form-1-last_timestep": self.march,
        }
        FormSet = formset_factory(CollectionSeasonForm, formset=CollectionSeasonFormSet)
        formset = FormSet(data, relation_field_name="seasons")
        self.assertFalse(formset.is_valid())
        self.assertEqual(
            formset.non_form_errors()[0],
            "The seasons must not overlap and must be given in order.",
        )

    def test_cleanup_after_save_does_not_delete_default_season(self):
        data = {
            "form-INITIAL_FORMS": 1,
            "form-TOTAL_FORMS": 2,
            "form-0-distribution": self.distribution,
            "form-0-first_timestep": self.january,
            "form-0-last_timestep": self.march,
            "form-1-distribution": self.distribution,
            "form-1-first_timestep": self.april,
            "form-1-last_timestep": self.december,
        }
        FormSet = formset_factory(CollectionSeasonForm, formset=CollectionSeasonFormSet)
        frequency = CollectionFrequency.objects.create(
            name="Test Frequency", type="Fixed"
        )
        formset = FormSet(data, parent_object=frequency, relation_field_name="seasons")
        formset.is_valid()
        self.assertTrue(formset.is_valid())
        formset.save()
        CollectionSeason.objects.get(
            distribution=self.distribution,
            first_timestep=self.january,
            last_timestep=self.december,
        )

    def test_formset_saves_collection_count_options(self):
        data = {
            "form-INITIAL_FORMS": 1,
            "form-TOTAL_FORMS": 1,
            "form-0-distribution": self.distribution,
            "form-0-first_timestep": self.january,
            "form-0-last_timestep": self.december,
            "form-0-standard": 100,
            "form-0-option_1": 150,
            "form-0-option_2": 200,
            "form-0-option_3": 250,
        }
        FormSet = formset_factory(CollectionSeasonForm, formset=CollectionSeasonFormSet)
        frequency = CollectionFrequency.objects.create(
            name="Test Frequency", type="Fixed"
        )
        formset = FormSet(data, parent_object=frequency, relation_field_name="seasons")
        self.assertTrue(formset.is_valid())
        formset.save()
        options = CollectionCountOptions.objects.get(
            frequency=frequency, season=formset.forms[0].instance
        )
        self.assertEqual(100, options.standard)
        self.assertEqual(150, options.option_1)
        self.assertEqual(200, options.option_2)
        self.assertEqual(250, options.option_3)


class CollectionModelFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.catchment = CollectionCatchment.objects.create(
            name="Catchment", publication_status="published"
        )
        cls.collector = Collector.objects.create(
            name="Collector", publication_status="published"
        )
        cls.collection_system = CollectionSystem.objects.create(
            name="System", publication_status="published"
        )
        cls.waste_category = WasteCategory.objects.create(
            name="Category", publication_status="published"
        )
        cls.material_group = MaterialCategory.objects.create(
            name="Biowaste component", publication_status="published"
        )
        cls.allowed_material_1 = WasteComponent.objects.create(
            name="Allowed Material 1", publication_status="published"
        )
        cls.allowed_material_1.categories.add(cls.material_group)
        cls.allowed_material_2 = WasteComponent.objects.create(
            name="Allowed Material 2", publication_status="published"
        )
        cls.allowed_material_2.categories.add(cls.material_group)
        cls.forbidden_material_1 = WasteComponent.objects.create(
            name="Forbidden Material 1", publication_status="published"
        )
        cls.forbidden_material_1.categories.add(cls.material_group)
        cls.forbidden_material_2 = WasteComponent.objects.create(
            name="Forbidden Material 2", publication_status="published"
        )
        cls.forbidden_material_2.categories.add(cls.material_group)
        cls.frequency = CollectionFrequency.objects.create(
            name="fix", publication_status="published"
        )
        waste_stream = WasteStream.objects.create(
            category=cls.waste_category, publication_status="published"
        )
        waste_stream.allowed_materials.set(
            [cls.allowed_material_1, cls.allowed_material_2]
        )
        waste_stream.forbidden_materials.set(
            [cls.forbidden_material_1, cls.forbidden_material_2]
        )
        cls.predecessor_collection_1 = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.collection_system,
            waste_stream=waste_stream,
            frequency=cls.frequency,
            valid_from=date(2021, 1, 1),
            publication_status="published",
        )
        cls.predecessor_collection_2 = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.collection_system,
            waste_stream=waste_stream,
            frequency=cls.frequency,
            valid_from=date(2022, 1, 1),
            publication_status="published",
        )
        cls.collection = Collection.objects.create(
            catchment=cls.catchment,
            collector=cls.collector,
            collection_system=cls.collection_system,
            waste_stream=waste_stream,
            frequency=cls.frequency,
            valid_from=date(2023, 1, 1),
            valid_until=date(2023, 12, 31),
            publication_status="published",
        )
        cls.collection.predecessors.set(
            [cls.predecessor_collection_1, cls.predecessor_collection_2]
        )

    def test_form_errors(self):
        data = {"connection_rate_year": 123}
        form = CollectionModelForm(
            instance=self.collection, data=dict_to_querydict(data)
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["catchment"][0], "This field is required.")
        self.assertEqual(form.errors["collection_system"][0], "This field is required.")
        self.assertEqual(form.errors["waste_category"][0], "This field is required.")
        self.assertEqual(form.errors["valid_from"][0], "This field is required.")

    def test_waste_stream_get_or_create_on_save(self):
        form = CollectionModelForm(
            data=dict_to_querydict(
                {
                    "catchment": self.catchment.id,
                    "collector": self.collector.id,
                    "collection_system": self.collection_system.id,
                    "waste_category": self.waste_category.id,
                    "allowed_materials": [
                        self.allowed_material_1.id,
                        self.allowed_material_2.id,
                    ],
                    "forbidden_materials": [
                        self.forbidden_material_1.id,
                        self.forbidden_material_2.id,
                    ],
                    "frequency": self.frequency.id,
                    "valid_from": date(2023, 1, 1),
                    "description": "This is a test case",
                    "connection_type": "VOLUNTARY",
                }
            )
        )
        self.assertTrue(form.is_valid())
        form.instance.owner = self.collection.owner
        instance = form.save()
        self.assertIsInstance(instance, Collection)
        self.assertEqual(
            instance.name,
            f"{self.catchment} {self.waste_category} {self.collection_system} {self.collection.valid_from.year}",
        )
        self.assertIsInstance(instance.waste_stream, WasteStream)
        self.assertEqual(instance.waste_stream.category.id, self.waste_category.id)

        equal_form = CollectionModelForm(
            data=dict_to_querydict(
                {
                    "catchment": self.catchment.id,
                    "collector": self.collector.id,
                    "collection_system": self.collection_system.id,
                    "waste_category": self.waste_category.id,
                    "allowed_materials": [
                        self.allowed_material_1.id,
                        self.allowed_material_2.id,
                    ],
                    "forbidden_materials": [
                        self.forbidden_material_1.id,
                        self.forbidden_material_2.id,
                    ],
                    "frequency": self.frequency.id,
                    "valid_from": date(2023, 1, 1),
                    "flyer_url": "https://www.great-test-flyers.com",
                    "description": "This is a test case",
                    "connection_type": "VOLUNTARY",
                }
            )
        )
        self.assertTrue(equal_form.is_valid())
        equal_form.instance.owner = self.collection.owner
        instance2 = equal_form.save()
        self.assertIsInstance(instance2.waste_stream, WasteStream)
        self.assertEqual(instance2.waste_stream.category.id, self.waste_category.id)
        self.assertEqual(instance2.waste_stream.id, instance.waste_stream.id)
        self.assertEqual(len(WasteStream.objects.all()), 1)

    def test_on_change_of_valid_from_date_predecessors_valid_until_date_is_updated(
        self,
    ):
        form = CollectionModelForm(
            instance=self.collection,
            data=dict_to_querydict(
                {
                    "catchment": self.catchment.id,
                    "collector": self.collector.id,
                    "collection_system": self.collection_system.id,
                    "waste_category": self.waste_category.id,
                    "allowed_materials": [
                        self.allowed_material_1.id,
                        self.allowed_material_2.id,
                    ],
                    "forbidden_materials": [
                        self.forbidden_material_1.id,
                        self.forbidden_material_2.id,
                    ],
                    "frequency": self.frequency.id,
                    "valid_from": date(2023, 1, 1),
                    "valid_until": date(2023, 12, 31),
                    "description": "This is a test case",
                    "connection_type": "VOLUNTARY",
                }
            ),
        )
        self.assertTrue(form.is_valid())
        form.save()
        self.predecessor_collection_1.refresh_from_db()
        self.predecessor_collection_2.refresh_from_db()
        self.assertEqual(self.predecessor_collection_1.valid_until, date(2022, 12, 31))
        self.assertEqual(self.predecessor_collection_2.valid_until, date(2022, 12, 31))

    def test_required_bin_capacity_field_present_and_valid(self):
        form = CollectionModelForm()
        self.assertIn("required_bin_capacity", form.fields)
        # Valid value
        data = {
            "catchment": self.catchment.id,
            "collector": self.collector.id,
            "collection_system": self.collection_system.id,
            "waste_category": self.waste_category.id,
            "allowed_materials": [
                self.allowed_material_1.id,
                self.allowed_material_2.id,
            ],
            "forbidden_materials": [
                self.forbidden_material_1.id,
                self.forbidden_material_2.id,
            ],
            "connection_type": "VOLUNTARY",
            "min_bin_size": 120,
            "required_bin_capacity": 5,
            "required_bin_capacity_reference": "person",
            "valid_from": date(2023, 1, 1),
        }
        form = CollectionModelForm(data=dict_to_querydict(data))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertEqual(instance.required_bin_capacity, 5)
        # Null/blank value
        data["required_bin_capacity"] = ""
        form = CollectionModelForm(data=dict_to_querydict(data))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertIsNone(instance.required_bin_capacity)

    def test_required_bin_capacity_reference_field_present_and_valid(self):
        form = CollectionModelForm()
        self.assertIn("required_bin_capacity_reference", form.fields)
        # Valid value
        data = {
            "catchment": self.catchment.id,
            "collector": self.collector.id,
            "collection_system": self.collection_system.id,
            "waste_category": self.waste_category.id,
            "allowed_materials": [
                self.allowed_material_1.id,
                self.allowed_material_2.id,
            ],
            "forbidden_materials": [
                self.forbidden_material_1.id,
                self.forbidden_material_2.id,
            ],
            "frequency": self.frequency.id,
            "min_bin_size": 120,
            "required_bin_capacity": 5,
            "required_bin_capacity_reference": "person",
            "valid_from": date(2023, 1, 1),
        }
        form = CollectionModelForm(data=dict_to_querydict(data))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertEqual(instance.required_bin_capacity_reference, "person")
        # Null/blank value
        data["required_bin_capacity_reference"] = ""
        form = CollectionModelForm(data=dict_to_querydict(data))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertIn(instance.required_bin_capacity_reference, [None, ""])

    def test_connection_type_field_accepts_all_choices(self):
        from case_studies.soilcom.forms import CONNECTION_TYPE_CHOICES

        valid_choices = [c[0] for c in CONNECTION_TYPE_CHOICES] + [None, ""]
        for value in valid_choices:
            data = {
                "catchment": self.catchment.id,
                "collector": self.collector.id,
                "collection_system": self.collection_system.id,
                "waste_category": self.waste_category.id,
                "allowed_materials": [],
                "forbidden_materials": [],
                "min_bin_size": 120,
                "required_bin_capacity": 5,
                "required_bin_capacity_reference": "person",
                "frequency": self.frequency.id,
                "valid_from": date(2023, 1, 1),
                "connection_type": value if value is not None else "",
            }
            form = CollectionModelForm(data=dict_to_querydict(data))
            self.assertTrue(
                form.is_valid(),
                f"Form should be valid for connection_type={value}: {form.errors}",
            )
            instance = form.save(commit=False)
            expected = value if value not in (None, "") else None
            if expected is None:
                self.assertIn(instance.connection_type, [None, ""])
            else:
                self.assertEqual(instance.connection_type, expected)
        # Check help_text
        form = CollectionModelForm()
        self.assertIn("not specified", form.fields["connection_type"].help_text)

        form = CollectionModelForm()
        self.assertIn("required_bin_capacity_reference", form.fields)
        # Valid value
        data = {
            "catchment": self.catchment.id,
            "collector": self.collector.id,
            "collection_system": self.collection_system.id,
            "waste_category": self.waste_category.id,
            "allowed_materials": [
                self.allowed_material_1.id,
                self.allowed_material_2.id,
            ],
            "forbidden_materials": [
                self.forbidden_material_1.id,
                self.forbidden_material_2.id,
            ],
            "connection_type": "VOLUNTARY",
            "min_bin_size": 120,
            "required_bin_capacity": 5,
            "required_bin_capacity_reference": "person",
            "valid_from": date(2023, 1, 1),
        }
        form = CollectionModelForm(data=dict_to_querydict(data))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertEqual(instance.required_bin_capacity_reference, "person")
        # Null/blank value
        data["required_bin_capacity_reference"] = ""
        form = CollectionModelForm(data=dict_to_querydict(data))
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        self.assertIn(instance.required_bin_capacity_reference, [None, ""])


class WasteFlyerUrlFormSetTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with mute_signals(signals.post_save):
            cls.flyer_1 = WasteFlyer.objects.create(url="https://www.test-flyers.org")
            cls.flyer_2 = WasteFlyer.objects.create(url="https://www.best-flyers.org")
            cls.flyer_3 = WasteFlyer.objects.create(url="https://www.rest-flyers.org")
        CollectionCatchment.objects.create(name="Catchment")
        collector = Collector.objects.create(name="Collector")
        cls.collection_system = CollectionSystem.objects.create(name="System")
        waste_category = WasteCategory.objects.create(name="Category")
        material_group = MaterialCategory.objects.create(name="Biowaste component")
        material1 = WasteComponent.objects.create(name="Material 1")
        material1.categories.add(material_group)
        material2 = WasteComponent.objects.create(name="Material 2")
        material2.categories.add(material_group)
        cls.waste_stream = WasteStream.objects.create(category=waste_category)
        cls.waste_stream.allowed_materials.set([material1, material2])
        cls.collection = Collection.objects.create(
            name="collection1",
            collector=collector,
            collection_system=cls.collection_system,
            waste_stream=cls.waste_stream,
        )
        cls.collection.flyers.set([cls.flyer_1, cls.flyer_2, cls.flyer_3])
        cls.collection2 = Collection.objects.create(
            name="collection2",
            collector=collector,
            collection_system=cls.collection_system,
            waste_stream=cls.waste_stream,
        )
        cls.collection2.flyers.set([cls.flyer_1, cls.flyer_2])

    def test_associated_flyer_urls_are_shown_as_initial_values(self):
        initial_urls = [{"url": flyer.url} for flyer in self.collection.flyers.all()]
        WasteFlyerModelFormSet = formset_factory(
            WasteFlyerModelForm, formset=WasteFlyerFormSet, extra=0
        )
        formset = WasteFlyerModelFormSet(
            parent_object=self.collection,
            initial=initial_urls,
            relation_field_name="flyers",
        )
        displayed_urls = [form.initial for form in formset]
        self.assertListEqual(initial_urls, displayed_urls)

    def test_initial_flyers_remain_associated_with_parent_collection(self):
        initial_urls = [{"url": flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            "form-INITIAL_FORMS": 3,
            "form-TOTAL_FORMS": 3,
            "form-0-url": initial_urls[0]["url"],
            "form-1-url": initial_urls[1]["url"],
            "form-2-url": initial_urls[2]["url"],
        }
        WasteFlyerModelFormSet = formset_factory(
            WasteFlyerModelForm, formset=WasteFlyerFormSet
        )
        formset = WasteFlyerModelFormSet(
            parent_object=self.collection, data=data, relation_field_name="flyers"
        )
        self.assertTrue(formset.is_valid())
        formset.save()
        for url in initial_urls:
            WasteFlyer.objects.get(url=url["url"])
        self.assertEqual(len(initial_urls), self.collection.flyers.count())

    def test_empty_url_field_is_ignored(self):
        data = {"form-INITIAL_FORMS": 1, "form-TOTAL_FORMS": 1, "form-0-url": ""}
        WasteFlyerModelFormSet = formset_factory(
            WasteFlyerModelForm, formset=WasteFlyerFormSet, extra=0
        )
        formset = WasteFlyerModelFormSet(
            data, parent_object=self.collection, relation_field_name="flyers"
        )
        self.assertTrue(formset.is_valid())
        formset.save()
        with self.assertRaises(WasteFlyer.DoesNotExist):
            WasteFlyer.objects.get(url="")

    def test_flyers_are_created_from_unknown_urls_and_associated_with_parent_collection(
        self,
    ):
        initial_urls = [{"url": flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            "form-INITIAL_FORMS": 3,
            "form-TOTAL_FORMS": 4,
            "form-0-url": initial_urls[0]["url"],
            "form-1-url": initial_urls[1]["url"],
            "form-2-url": initial_urls[2]["url"],
            "form-3-url": "https://www.fest-flyers.org",
        }
        WasteFlyerModelFormSet = formset_factory(
            WasteFlyerModelForm, formset=WasteFlyerFormSet
        )
        formset = WasteFlyerModelFormSet(
            data, parent_object=self.collection, relation_field_name="flyers"
        )
        self.assertTrue(formset.is_valid())
        with mute_signals(signals.post_save):
            formset.save()
        WasteFlyer.objects.get(url="https://www.fest-flyers.org")
        self.assertEqual(len(initial_urls) + 1, self.collection.flyers.count())

    def test_flyers_removed_from_this_collection_but_connected_to_another_are_preserved(
        self,
    ):
        initial_urls = [{"url": flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            "form-INITIAL_FORMS": 3,
            "form-TOTAL_FORMS": 3,
            "form-0-url": initial_urls[0]["url"],
            "form-1-url": "",
            "form-2-url": initial_urls[2]["url"],
        }
        WasteFlyerModelFormSet = formset_factory(
            WasteFlyerModelForm, formset=WasteFlyerFormSet
        )
        formset = WasteFlyerModelFormSet(
            data, parent_object=self.collection, relation_field_name="flyers"
        )
        self.assertTrue(formset.is_valid())
        original_flyer_count = WasteFlyer.objects.count()
        formset.save()
        WasteFlyer.objects.get(url=initial_urls[1]["url"])
        self.assertEqual(original_flyer_count - 1, self.collection.flyers.count())
        self.assertEqual(original_flyer_count, WasteFlyer.objects.count())

    def test_completely_unused_flyers_get_deleted(self):
        initial_urls = [{"url": flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            "form-INITIAL_FORMS": 3,
            "form-TOTAL_FORMS": 3,
            "form-0-url": initial_urls[0]["url"],
            "form-1-url": initial_urls[1]["url"],
            "form-2-url": "",
        }
        WasteFlyerModelFormSet = formset_factory(
            WasteFlyerModelForm, formset=WasteFlyerFormSet
        )
        formset = WasteFlyerModelFormSet(
            data, parent_object=self.collection, relation_field_name="flyers"
        )
        self.assertTrue(formset.is_valid())
        original_flyer_count = WasteFlyer.objects.count()
        formset.save()
        with self.assertRaises(WasteFlyer.DoesNotExist):
            WasteFlyer.objects.get(url=initial_urls[2]["url"])
        self.assertEqual(original_flyer_count - 1, WasteFlyer.objects.count())
        self.assertEqual(original_flyer_count - 1, self.collection.flyers.count())

    def test_save_two_new_and_equal_urls_only_once(self):
        WasteFlyerModelFormSet = formset_factory(
            WasteFlyerModelForm, formset=WasteFlyerFormSet
        )
        url = "https://www.fest-flyers.org"
        data = {
            "form-INITIAL_FORMS": "0",
            "form-TOTAL_FORMS": "2",
            "form-0-url": url,
            "form-1-url": url,
        }
        formset = WasteFlyerModelFormSet(
            data, parent_object=self.collection, relation_field_name="flyers"
        )
        self.assertTrue(formset.is_valid())
        original_flyer_count = WasteFlyer.objects.count()
        with mute_signals(signals.post_save):
            formset.save()
        # get raises an error if the query returns more than one instance
        WasteFlyer.objects.get(url=url)
        # one should be deleted and one created ==> +-0
        self.assertEqual(original_flyer_count, WasteFlyer.objects.count())

    def test_flyer_referenced_by_property_value_is_not_deleted(self):
        """Test that a flyer referenced by a CollectionPropertyValue is not deleted."""
        from utils.properties.models import Property, Unit

        from ..models import CollectionPropertyValue

        # Create a property value that references a flyer via sources
        unit = Unit.objects.create(name="Test Unit")
        prop = Property.objects.create(name="Test Property", unit="kg")
        prop_value = CollectionPropertyValue.objects.create(
            name="Test Property Value",
            collection=self.collection,
            property=prop,
            unit=unit,
            average=10.0,
        )
        prop_value.sources.add(self.flyer_1)

        # Remove flyer_1 from collection's flyers
        initial_urls = [{"url": flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            "form-INITIAL_FORMS": 3,
            "form-TOTAL_FORMS": 3,
            "form-0-url": initial_urls[1]["url"],  # Keep flyer_2
            "form-1-url": initial_urls[2]["url"],  # Keep flyer_3
            "form-2-url": "",  # Remove flyer_1 from collection
        }
        WasteFlyerModelFormSet = formset_factory(
            WasteFlyerModelForm, formset=WasteFlyerFormSet
        )
        formset = WasteFlyerModelFormSet(
            data, parent_object=self.collection, relation_field_name="flyers"
        )
        self.assertTrue(formset.is_valid())
        formset.save()

        # flyer_1 should still exist because it's referenced by prop_value
        WasteFlyer.objects.get(pk=self.flyer_1.pk)
        # It should be removed from collection.flyers
        self.assertEqual(2, self.collection.flyers.count())
        self.assertNotIn(self.flyer_1, self.collection.flyers.all())

    def test_flyer_referenced_by_aggregated_property_value_is_not_deleted(self):
        """Test that a flyer referenced by AggregatedCollectionPropertyValue is not deleted."""
        from utils.properties.models import Property, Unit

        from ..models import AggregatedCollectionPropertyValue

        # Create aggregated property value that references a flyer via sources
        unit = Unit.objects.create(name="Test Unit 2", publication_status="published")
        prop = Property.objects.create(
            name="Test Property 2", unit="kg", publication_status="published"
        )
        prop.allowed_units.add(unit)
        agg_prop_value = AggregatedCollectionPropertyValue.objects.create(
            name="Test Aggregated Property Value",
            property=prop,
            unit=unit,
            average=20.0,
            year=2024,
        )
        agg_prop_value.sources.add(self.flyer_2)

        # Remove flyer_2 from collection's flyers
        initial_urls = [{"url": flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            "form-INITIAL_FORMS": 3,
            "form-TOTAL_FORMS": 3,
            "form-0-url": initial_urls[0]["url"],  # Keep flyer_1
            "form-1-url": "",  # Remove flyer_2 from collection
            "form-2-url": initial_urls[2]["url"],  # Keep flyer_3
        }
        WasteFlyerModelFormSet = formset_factory(
            WasteFlyerModelForm, formset=WasteFlyerFormSet
        )
        formset = WasteFlyerModelFormSet(
            data, parent_object=self.collection, relation_field_name="flyers"
        )
        self.assertTrue(formset.is_valid())
        formset.save()

        # flyer_2 should still exist because it's referenced by agg_prop_value
        WasteFlyer.objects.get(pk=self.flyer_2.pk)
        # It should be removed from collection.flyers
        self.assertEqual(2, self.collection.flyers.count())
        self.assertNotIn(self.flyer_2, self.collection.flyers.all())

    def test_flyer_referenced_as_generic_source_is_not_deleted(self):
        """Test that a flyer used as a generic Source elsewhere is not deleted."""
        # Add flyer_3 to collection2's sources (as generic Source, not as flyer)
        self.collection2.sources.add(self.flyer_3)

        # Remove flyer_3 from collection's flyers
        initial_urls = [{"url": flyer.url} for flyer in self.collection.flyers.all()]
        data = {
            "form-INITIAL_FORMS": 3,
            "form-TOTAL_FORMS": 3,
            "form-0-url": initial_urls[0]["url"],  # Keep flyer_1
            "form-1-url": initial_urls[1]["url"],  # Keep flyer_2
            "form-2-url": "",  # Remove flyer_3 from collection
        }
        WasteFlyerModelFormSet = formset_factory(
            WasteFlyerModelForm, formset=WasteFlyerFormSet
        )
        formset = WasteFlyerModelFormSet(
            data, parent_object=self.collection, relation_field_name="flyers"
        )
        self.assertTrue(formset.is_valid())
        formset.save()

        # flyer_3 should still exist because it's referenced by collection2.sources
        WasteFlyer.objects.get(pk=self.flyer_3.pk)
        # It should be removed from collection.flyers
        self.assertEqual(2, self.collection.flyers.count())
        self.assertNotIn(self.flyer_3, self.collection.flyers.all())


class CollectionAddWasteSampleFormTestCase(TestCase):
    def setUp(self):
        self.material = Material.objects.create(
            name="Test Material", publication_status="published"
        )
        self.sample = Sample.objects.create(
            name="Test Sample",
            material=self.material,
            series=SampleSeries.objects.create(
                name="Test Series",
                material=self.material,
                publication_status="published",
            ),
            publication_status="published",
        )

    def test_form_is_valid_with_existing_sample(self):
        form = CollectionAddWasteSampleForm(data={"sample": self.sample.id})
        self.assertTrue(form.is_valid())

    def test_form_is_invalid_with_non_existing_sample(self):
        form = CollectionAddWasteSampleForm(data={"sample": 9999})
        self.assertFalse(form.is_valid())

    def test_form_is_invalid_with_no_sample(self):
        form = CollectionAddWasteSampleForm(data={})
        self.assertFalse(form.is_valid())


class CollectionRemoveWasteSampleFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        CollectionCatchment.objects.create(name="Catchment")
        collector = Collector.objects.create(name="Collector")
        collection_system = CollectionSystem.objects.create(name="System")
        waste_stream = WasteStream.objects.create(
            category=WasteCategory.objects.create(name="Category")
        )
        cls.collection = Collection.objects.create(
            name="collection1",
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
        )
        cls.material = Material.objects.create(name="Test Material")
        cls.sample = Sample.objects.create(
            name="Test Sample",
            material=cls.material,
            series=SampleSeries.objects.create(
                name="Test Series", material=cls.material
            ),
        )

    def test_collection_remove_waste_sample_form_valid(self):
        self.collection.samples.add(self.sample)
        form = CollectionRemoveWasteSampleForm(
            data={"sample": self.sample.id}, instance=self.collection
        )
        self.assertTrue(form.is_valid())

    def test_collection_remove_waste_sample_form_invalid_with_existing_but_unassociated_sample(
        self,
    ):
        form = CollectionRemoveWasteSampleForm(
            data={"sample": self.sample.id}, instance=self.collection
        )
        self.assertFalse(form.is_valid())

    def test_collection_remove_waste_sample_form_invalid(self):
        form = CollectionRemoveWasteSampleForm(
            data={"sample": None}, instance=self.collection
        )
        self.assertFalse(form.is_valid())

    def test_collection_remove_waste_sample_form_no_sample_in_collection(self):
        material = Material.objects.create(name="Other Material")
        other_sample = Sample.objects.create(
            name="Other Sample",
            material=material,
            series=SampleSeries.objects.create(name="Other Series", material=material),
        )
        form = CollectionRemoveWasteSampleForm(
            data={"sample": other_sample.id}, instance=self.collection
        )
        self.assertFalse(form.is_valid())

    def test_collection_remove_waste_sample_form_sample_queryset(self):
        self.collection.samples.add(self.sample)
        form = CollectionRemoveWasteSampleForm(instance=self.collection)
        self.assertTrue(form.fields["sample"].queryset.exists())
        self.assertEqual(form.fields["sample"].queryset.first(), self.sample)


class CollectionAddPredecessorFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        catchment1 = CollectionCatchment.objects.create(
            name="Catchment 1", publication_status="published"
        )
        catchment2 = CollectionCatchment.objects.create(
            name="Catchment 2", publication_status="published"
        )
        collector = Collector.objects.create(
            name="Collector", publication_status="published"
        )
        collection_system = CollectionSystem.objects.create(
            name="System", publication_status="published"
        )
        waste_stream = WasteStream.objects.create(
            category=WasteCategory.objects.create(
                name="Category", publication_status="published"
            ),
            publication_status="published",
        )
        cls.collection = Collection.objects.create(
            name="Current Collection",
            catchment=catchment1,
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
            publication_status="published",
        )
        cls.other_collection = Collection.objects.create(
            name="Predecessor Collection",
            catchment=catchment1,
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
            publication_status="published",
        )
        cls.predecessor_collection = Collection.objects.create(
            name="Predecessor Collection",
            catchment=catchment2,
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
            publication_status="published",
        )

    def test_queryset_excludes_current_collection(self):
        form = CollectionAddPredecessorForm(instance=self.collection)
        self.assertFalse(
            form.fields["predecessor"].queryset.filter(id=self.collection.id).exists()
        )

    def test_form_is_valid_with_existing_predecessor(self):
        form = CollectionAddPredecessorForm(
            data={"predecessor": self.predecessor_collection.id}
        )
        form.is_valid()
        self.assertTrue(form.is_valid())

    def test_form_is_invalid_with_non_existing_predecessor(self):
        form = CollectionAddPredecessorForm(data={"predecessor": 9999})
        self.assertFalse(form.is_valid())

    def test_form_is_invalid_with_no_predecessor(self):
        form = CollectionAddPredecessorForm(data={})
        self.assertFalse(form.is_valid())

    def collections_with_same_catchment_are_prioritized(self):
        form = CollectionAddPredecessorForm(instance=self.collection)
        queryset = form.fields["predecessor"].queryset
        self.assertEqual(queryset.first(), self.other_collection)

    def current_collection_is_excluded_from_queryset(self):
        form = CollectionAddPredecessorForm(instance=self.collection)
        queryset = form.fields["predecessor"].queryset
        self.assertNotIn(self.collection, queryset)

    def collections_with_different_catchment_are_included_in_queryset(self):
        form = CollectionAddPredecessorForm(instance=self.collection)
        queryset = form.fields["predecessor"].queryset
        self.assertIn(self.predecessor_collection, queryset)


class CollectionRemovePredecessorFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        CollectionCatchment.objects.create(name="Catchment")
        collector = Collector.objects.create(name="Collector")
        collection_system = CollectionSystem.objects.create(name="System")
        waste_stream = WasteStream.objects.create(
            category=WasteCategory.objects.create(name="Category")
        )
        cls.collection = Collection.objects.create(
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
        )
        cls.predecessor_collection = Collection.objects.create(
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
        )
        cls.other_collection = Collection.objects.create(
            collector=collector,
            collection_system=collection_system,
            waste_stream=waste_stream,
        )

    def test_collection_remove_predecessor_form_valid(self):
        self.collection.add_predecessor(self.predecessor_collection)
        form = CollectionRemovePredecessorForm(
            data={"predecessor": self.predecessor_collection.id},
            instance=self.collection,
        )
        self.assertTrue(form.is_valid())

    def test_collection_remove_predecessor_form_invalid_with_existing_but_unassociated_collection(
        self,
    ):
        form = CollectionRemovePredecessorForm(
            data={"predecessor": self.other_collection.id}, instance=self.collection
        )
        self.assertFalse(form.is_valid())

    def test_collection_remove_predecessor_form_invalid(self):
        form = CollectionRemovePredecessorForm(
            data={"predecessor": None}, instance=self.collection
        )
        self.assertFalse(form.is_valid())

    def test_collection_remove_predecessor_form_no_predecessor_in_collection(self):
        form = CollectionRemovePredecessorForm(
            data={"predecessor": self.other_collection.id}, instance=self.collection
        )
        self.assertFalse(form.is_valid())

    def test_collection_remove_predecessor_form_predecessor_queryset(self):
        self.collection.add_predecessor(self.predecessor_collection)
        form = CollectionRemovePredecessorForm(instance=self.collection)
        self.assertTrue(form.fields["predecessor"].queryset.exists())
        self.assertEqual(
            form.fields["predecessor"].queryset.first(), self.predecessor_collection
        )

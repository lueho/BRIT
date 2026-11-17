from types import SimpleNamespace

from django import forms
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from sources.waste_collection.models import Collection
from utils.object_management.models import User
from utils.properties.forms import PropertyModelForm
from utils.properties.models import Property, Unit

from ..forms import UserCreatedObjectFormMixin


class CollectionChoiceForm(UserCreatedObjectFormMixin, forms.Form):
    choice = forms.ModelChoiceField(queryset=Collection.objects.all())

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)


class UserCreatedObjectFormMixinChoiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="form-choice-owner")
        cls.outsider = User.objects.create_user(username="form-choice-outsider")
        cls.private_collection = Collection.objects.create(
            name="Private form choice",
            owner=cls.owner,
            publication_status="private",
        )
        cls.unit_1 = Unit.objects.create(
            name="Existing form unit",
            symbol="ef",
            owner=cls.owner,
            publication_status="private",
        )
        cls.unit_2 = Unit.objects.create(
            name="New form unit",
            symbol="nf",
            owner=cls.owner,
            publication_status="private",
        )
        cls.unreadable_unit = Unit.objects.create(
            name="Unreadable form unit",
            symbol="uf",
            owner=cls.outsider,
            publication_status="private",
        )
        cls.property = Property.objects.create(
            name="Form choice property",
            owner=cls.owner,
            publication_status="private",
        )
        cls.property.allowed_units.add(cls.unit_1)

    def test_get_choices_are_filtered_for_anonymous_user(self):
        form = CollectionChoiceForm(
            request=SimpleNamespace(user=AnonymousUser()),
        )

        self.assertFalse(
            form.fields["choice"]
            .queryset.filter(pk=self.private_collection.pk)
            .exists()
        )

    def test_owner_can_see_private_choice_on_get(self):
        form = CollectionChoiceForm(
            request=SimpleNamespace(user=self.owner),
        )

        self.assertTrue(
            form.fields["choice"]
            .queryset.filter(pk=self.private_collection.pk)
            .exists()
        )

    def test_update_form_keeps_existing_choice(self):
        instance = SimpleNamespace(pk=123, choice=self.private_collection)
        form = CollectionChoiceForm(
            instance=instance,
            request=SimpleNamespace(user=self.outsider),
        )

        self.assertTrue(
            form.fields["choice"]
            .queryset.filter(pk=self.private_collection.pk)
            .exists()
        )

    def test_invisible_posted_choice_is_rejected(self):
        form = CollectionChoiceForm(
            data={"choice": str(self.private_collection.pk)},
            request=SimpleNamespace(user=self.outsider),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("choice", form.errors)

    def test_missing_request_uses_anonymous_visibility(self):
        form = CollectionChoiceForm()

        self.assertFalse(
            form.fields["choice"]
            .queryset.filter(pk=self.private_collection.pk)
            .exists()
        )

    def test_dict_multiple_choice_values_keep_new_readable_units(self):
        form = PropertyModelForm(
            data={
                "name": "Updated form choice property",
                "allowed_units": [self.unit_1.pk, self.unit_2.pk],
                "description": self.property.description,
            },
            instance=self.property,
            request=SimpleNamespace(user=self.owner),
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertCountEqual(
            form.cleaned_data["allowed_units"], [self.unit_1, self.unit_2]
        )
        form.save()
        self.assertCountEqual(
            self.property.allowed_units.all(), [self.unit_1, self.unit_2]
        )

    def test_dict_multiple_choice_values_reject_unreadable_units(self):
        form = PropertyModelForm(
            data={
                "name": "Updated form choice property",
                "allowed_units": [self.unit_1.pk, self.unreadable_unit.pk],
                "description": self.property.description,
            },
            instance=self.property,
            request=SimpleNamespace(user=self.owner),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("allowed_units", form.errors)

from types import SimpleNamespace

from django import forms
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from sources.waste_collection.models import Collection
from utils.object_management.models import User

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

from crispy_forms.helper import FormHelper
from django.test import TestCase

from ..filters import (
    BaseCrispyFilterSet,
    NullablePercentageRangeFilter,
    NullableRangeFilter,
)
from .models import DummyModel


class CustomFormHelper(FormHelper):
    pass


class DummyFilterSet(BaseCrispyFilterSet):
    class Meta:
        model = DummyModel
        fields = ("test_field",)
        form_helper = CustomFormHelper


class BaseCrispyFilterSetTestCase(TestCase):

    def test_get_form_helper(self):
        filter_set = DummyFilterSet(queryset=DummyModel.objects.all())
        self.assertIsInstance(filter_set.get_form_helper(), CustomFormHelper)

        class CustomFilterSetWithoutFormHelper(BaseCrispyFilterSet):
            class Meta:
                model = DummyModel
                fields = ("test_field",)

        filter_set = CustomFilterSetWithoutFormHelper(queryset=DummyModel.objects.all())
        self.assertIsInstance(filter_set.get_form_helper(), FormHelper)

    def test_form(self):
        filter_set = DummyFilterSet(queryset=DummyModel.objects.all())
        form = filter_set.form
        self.assertFalse(form.helper.form_tag)


class TestNullableRangeFilter(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.one = DummyModel.objects.create(test_field=1)
        cls.fifty = DummyModel.objects.create(test_field=50)
        cls.hundred = DummyModel.objects.create(test_field=100)
        cls.none = DummyModel.objects.create(test_field=None)

    def test_filter_with_null_value(self):
        range_with_null_flag = (slice(20, 90), True)
        filter_ = NullableRangeFilter(field_name="test_field")
        result = filter_.filter(DummyModel.objects.all(), range_with_null_flag)
        expected = DummyModel.objects.filter(id__in=[self.fifty.id, self.none.id])
        self.assertQuerySetEqual(result, expected, ordered=False)

    def test_filter_without_null_value(self):
        range_with_null_flag = (slice(20, 100), False)
        filter_ = NullableRangeFilter(field_name="test_field")
        result = filter_.filter(DummyModel.objects.all(), range_with_null_flag)
        expected = DummyModel.objects.filter(id__in=[self.fifty.id, self.hundred.id])
        self.assertQuerySetEqual(result, expected, ordered=False)


class NullablePercentageRangeFilterTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.ten = DummyModel.objects.create(test_field=0.1)
        cls.fifty = DummyModel.objects.create(test_field=0.5)
        cls.hundred = DummyModel.objects.create(test_field=1.0)
        cls.none = DummyModel.objects.create(test_field=None)

    def test_filter_with_null_value(self):
        range_with_null_flag = (slice(20, 90), True)
        filter_ = NullablePercentageRangeFilter(field_name="test_field")
        result = filter_.filter(DummyModel.objects.all(), range_with_null_flag)
        expected = DummyModel.objects.filter(id__in=[self.fifty.id, self.none.id])
        self.assertQuerySetEqual(result, expected, ordered=False)

    def test_filter_without_null_value(self):
        range_with_null_flag = (slice(20, 100), False)
        filter_ = NullablePercentageRangeFilter(field_name="test_field")
        result = filter_.filter(DummyModel.objects.all(), range_with_null_flag)
        expected = DummyModel.objects.filter(id__in=[self.fifty.id, self.hundred.id])
        self.assertQuerySetEqual(result, expected, ordered=False)

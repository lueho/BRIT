from crispy_forms.helper import FormHelper
from django.contrib.auth.models import AnonymousUser, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.test import TestCase
from factory.django import mute_signals

from case_studies.soilcom.models import Collection
from utils.object_management.models import UserCreatedObject

from ..filters import (
    BaseCrispyFilterSet,
    NullablePercentageRangeFilter,
    NullableRangeFilter,
    UserCreatedObjectScopedFilterSet,
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

    def test_filter_null_only(self):
        range_with_null_flag = (slice(None, None), True)
        filter_ = NullableRangeFilter(field_name="test_field")
        result = filter_.filter(DummyModel.objects.all(), range_with_null_flag)
        expected = DummyModel.objects.all()
        self.assertQuerySetEqual(result, expected, ordered=False)

    def test_filter_no_range_no_null(self):
        range_with_null_flag = (slice(None, None), False)
        filter_ = NullableRangeFilter(field_name="test_field")
        filter_.default_range_min = None
        filter_.default_range_max = None
        result = filter_.filter(DummyModel.objects.all(), range_with_null_flag)
        expected = DummyModel.objects.all()
        self.assertQuerySetEqual(result, expected, ordered=False)

    def test_filter_no_range_defaults(self):
        range_with_null_flag = (slice(None, None), False)
        filter_ = NullableRangeFilter(field_name="test_field")
        result = filter_.filter(DummyModel.objects.all(), range_with_null_flag)
        expected = DummyModel.objects.filter(
            id__in=[self.one.id, self.fifty.id, self.hundred.id]
        )
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

    def test_filter_null_only(self):
        range_with_null_flag = (slice(None, None), True)
        filter_ = NullablePercentageRangeFilter(field_name="test_field")
        result = filter_.filter(DummyModel.objects.all(), range_with_null_flag)
        expected = DummyModel.objects.all()
        self.assertQuerySetEqual(result, expected, ordered=False)

    def test_filter_no_range_no_null(self):
        range_with_null_flag = (slice(None, None), False)
        filter_ = NullablePercentageRangeFilter(field_name="test_field")
        filter_.default_range_min = None
        filter_.default_range_max = None
        result = filter_.filter(DummyModel.objects.all(), range_with_null_flag)
        expected = DummyModel.objects.all()
        self.assertQuerySetEqual(result, expected, ordered=False)

    def test_filter_no_range_defaults(self):
        range_with_null_flag = (slice(None, None), False)
        filter_ = NullablePercentageRangeFilter(field_name="test_field")
        result = filter_.filter(DummyModel.objects.all(), range_with_null_flag)
        expected = DummyModel.objects.filter(
            id__in=[self.ten.id, self.fifty.id, self.hundred.id]
        )
        self.assertQuerySetEqual(result, expected, ordered=False)


class CollectionScopeFilterSet(UserCreatedObjectScopedFilterSet):
    class Meta:
        model = Collection
        fields = ("scope",)


class UserCreatedObjectScopedFilterSetTestCase(TestCase):
    """Regression tests for scope filtering on user-created objects."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="owner")
        cls.other_user = User.objects.create_user(username="other")
        cls.moderator = User.objects.create_user(username="moderator")
        cls.staff_user = User.objects.create_user(username="staff", is_staff=True)

        content_type = ContentType.objects.get_for_model(Collection)
        permission, _ = Permission.objects.get_or_create(
            codename="can_moderate_collection",
            content_type=content_type,
            defaults={"name": "Can moderate collections"},
        )
        cls.moderator.user_permissions.add(permission)

        with mute_signals(post_save):
            cls.owner_review = Collection.objects.create(
                name="Owner Review",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.other_review = Collection.objects.create(
                name="Other Review",
                owner=cls.other_user,
                publication_status=UserCreatedObject.STATUS_REVIEW,
            )
            cls.owner_published = Collection.objects.create(
                name="Owner Published",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PUBLISHED,
            )
            cls.owner_private = Collection.objects.create(
                name="Owner Private",
                owner=cls.owner,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )
            cls.other_private = Collection.objects.create(
                name="Other Private",
                owner=cls.other_user,
                publication_status=UserCreatedObject.STATUS_PRIVATE,
            )

    def _filtered_ids(self, user, scope):
        class RequestLike:
            def __init__(self, user_obj):
                self.user = user_obj

        filterset = CollectionScopeFilterSet(
            data={"scope": scope},
            queryset=Collection.objects.all(),
            request=RequestLike(user),
        )
        return set(filterset.qs.values_list("id", flat=True))

    def test_review_scope_for_regular_user_is_owner_only(self):
        result_ids = self._filtered_ids(self.owner, "review")
        self.assertEqual(result_ids, {self.owner_review.id})

    def test_review_scope_for_moderator_includes_all_review_objects(self):
        result_ids = self._filtered_ids(self.moderator, "review")
        self.assertEqual(result_ids, {self.owner_review.id, self.other_review.id})

    def test_review_scope_for_anonymous_returns_empty(self):
        result_ids = self._filtered_ids(AnonymousUser(), "review")
        self.assertEqual(result_ids, set())

    def test_private_scope_for_regular_user_is_owner_only(self):
        result_ids = self._filtered_ids(self.owner, "private")
        self.assertEqual(
            result_ids,
            {self.owner_review.id, self.owner_published.id, self.owner_private.id},
        )

    def test_private_scope_for_staff_user_is_owner_only(self):
        result_ids = self._filtered_ids(self.staff_user, "private")
        self.assertEqual(result_ids, set())

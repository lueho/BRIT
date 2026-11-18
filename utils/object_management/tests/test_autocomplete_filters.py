from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from inventories.models import InventoryAlgorithm
from maps.models import GeoDataset, Region
from materials.models import Material, Sample

VIEWS_LOGGER = "utils.object_management.views"


def _result_ids(response):
    return [item["id"] for item in response.json()["results"]]


def _hash_prefix(user):
    """Return a prefix of the user's real stored password hash."""
    return user.password[:8]


class AutocompleteRequestLookupOracleTests(TestCase):
    """Request-supplied TomSelect filters must not reach arbitrary ORM paths."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="oracle-admin", email="admin@example.com", is_staff=True
        )
        cls.other = User.objects.create_user(
            username="oracle-other", email="other@example.com"
        )
        cls.alpha = Material.objects.create(
            name="Alpha oracle material",
            owner=cls.admin,
            publication_status="published",
        )
        cls.beta = Material.objects.create(
            name="Beta oracle material",
            owner=cls.other,
            publication_status="published",
        )
        Sample.objects.create(
            name="Secret private sample",
            material=cls.alpha,
            owner=cls.admin,
            publication_status="private",
        )

    def _material_autocomplete(self, **params):
        return self.client.get(reverse("material-autocomplete"), params)

    def assert_no_oracle(self, lookup, correct, wrong):
        with self.assertLogs(VIEWS_LOGGER, level="WARNING") as logs:
            hit = self._material_autocomplete(f=f"{lookup}={correct}")
            miss = self._material_autocomplete(f=f"{lookup}={wrong}")
        self.assertIn("Rejected TomSelect filter lookup", logs.output[0])
        self.assertEqual(hit.status_code, 200)
        self.assertEqual(miss.status_code, 200)
        self.assertEqual(_result_ids(hit), _result_ids(miss))
        self.assertNotIn(self.alpha.pk, _result_ids(hit))

    def test_anonymous_cannot_probe_owner_password_hash(self):
        self.assert_no_oracle(
            "owner__password__startswith", _hash_prefix(self.admin), "zzz"
        )

    def test_anonymous_cannot_probe_owner_email(self):
        self.assert_no_oracle("owner__email__startswith", "admin@", "nobody@")

    def test_anonymous_cannot_probe_private_related_records(self):
        self.assert_no_oracle("samples__name__startswith", "Secret", "Nothing")

    def test_widget_prefixed_lookup_cannot_probe_owner_password_hash(self):
        self.assert_no_oracle(
            "x__owner__password__startswith", _hash_prefix(self.admin), "zzz"
        )

    def test_request_ordering_cannot_sort_by_owner_password_hash(self):
        default = self._material_autocomplete()
        by_hash = self._material_autocomplete(ordering="owner__password")
        self.assertEqual(_result_ids(default), [self.alpha.pk, self.beta.pk])
        self.assertEqual(_result_ids(by_hash), _result_ids(default))

    def test_scope_filter_still_applies(self):
        response = self._material_autocomplete(f="scope__name=published")
        self.assertEqual(_result_ids(response), [self.alpha.pk, self.beta.pk])


class UserAutocompleteLookupOracleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.target = User.objects.create_user(username="target-admin")
        cls.member = User.objects.create_user(username="plain-member")

    def test_authenticated_user_cannot_probe_password_hashes(self):
        self.client.force_login(self.member)
        url = reverse("user-autocomplete")
        hit = self.client.get(
            url, {"f": f"x__password__startswith={_hash_prefix(self.target)}"}
        )
        miss = self.client.get(url, {"f": "x__password__startswith=zzz"})
        self.assertEqual(_result_ids(hit), _result_ids(miss))
        self.assertNotIn(self.target.pk, _result_ids(hit))

    def test_exclude_cannot_probe_password_hashes(self):
        self.client.force_login(self.member)
        url = reverse("user-autocomplete")
        hit = self.client.get(
            url, {"e": f"x__password__startswith={_hash_prefix(self.target)}"}
        )
        miss = self.client.get(url, {"e": "x__password__startswith=zzz"})
        self.assertEqual(_result_ids(hit), _result_ids(miss))


class InventoryAlgorithmAutocompleteLookupOracleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = owner = User.objects.create_user(username="dataset-owner")
        region = Region.objects.create(name="Oracle region")
        geodataset = GeoDataset.objects.create(
            name="Oracle dataset",
            region=region,
            owner=owner,
            publication_status="published",
        )
        cls.algorithm = InventoryAlgorithm.objects.create(
            name="Oracle algorithm", geodataset=geodataset
        )

    def test_anonymous_cannot_probe_related_owner_password_hash(self):
        url = reverse("inventoryalgorithm-autocomplete")
        lookup = "x__geodataset__owner__password__startswith"
        hit = self.client.get(url, {"f": f"{lookup}={_hash_prefix(self.owner)}"})
        miss = self.client.get(url, {"f": f"{lookup}=zzz"})
        self.assertEqual(_result_ids(hit), _result_ids(miss))
        self.assertNotIn(self.algorithm.pk, _result_ids(hit))

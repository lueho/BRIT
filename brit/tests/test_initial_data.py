import importlib
import io
import os
from unittest import mock

from cookie_consent.models import Cookie, CookieGroup
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from brit.management.commands import ensure_initial_data as ensure_command_module
from brit.management.commands.ensure_initial_data import (
    Command as EnsureInitialDataCommand,
)
from distributions.models import Period, TemporalDistribution, Timestep
from maps.models import GeoDataset, MapConfiguration
from materials.models import (
    MaterialCategory,
    MaterialComponent,
    MaterialComponentGroup,
)
from sources.waste_collection.models import (
    Collection,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionSeason,
    WasteComponent,
)
from users.utils import ensure_initial_data as ensure_users_data
from utils.object_management.models import get_default_owner
from utils.properties.models import Property, Unit
from utils.properties.utils import ensure_initial_data as ensure_properties_data


class InitializerDependencyOrderingTests(SimpleTestCase):
    def setUp(self):
        self.command = EnsureInitialDataCommand()

    def test_declared_dependencies_determine_initialization_order(self):
        ordered = [
            label
            for label, _ in self.command.topological_sort(
                self.command.discover_initializers()
            )
        ]

        for label in (
            "users",
            "object_management",
            "properties",
            "materials",
            "distributions",
            "maps",
            "waste_collection",
            "brit",
        ):
            self.assertIn(label, ordered)

        self.assertLess(ordered.index("users"), ordered.index("object_management"))
        self.assertLess(ordered.index("object_management"), ordered.index("properties"))
        self.assertLess(ordered.index("object_management"), ordered.index("maps"))
        self.assertLess(ordered.index("properties"), ordered.index("maps"))
        self.assertLess(ordered.index("object_management"), ordered.index("materials"))
        self.assertLess(
            ordered.index("object_management"), ordered.index("distributions")
        )
        self.assertLess(
            ordered.index("distributions"), ordered.index("waste_collection")
        )
        self.assertLess(ordered.index("materials"), ordered.index("waste_collection"))

    def test_traversal_order_is_deterministic(self):
        initializers = self.command.discover_initializers()

        first = [label for label, _ in self.command.topological_sort(initializers)]
        second = [
            label
            for label, _ in self.command.topological_sort(list(reversed(initializers)))
        ]

        self.assertEqual(first, second)

    def test_circular_dependencies_raise_command_error(self):
        with self.assertRaises(CommandError):
            self.command.topological_sort(
                [
                    ("users", lambda: None, ["object_management"]),
                    ("object_management", lambda: None, ["users"]),
                ]
            )

    def test_unknown_dependency_label_raises_command_error(self):
        with self.assertRaises(CommandError):
            self.command.topological_sort(
                [("properties", lambda: None, ["utils.object_management"])]
            )

    def test_installed_but_unselected_dependency_is_allowed(self):
        ordered = self.command.topological_sort(
            [("properties", lambda: None, ["object_management"])]
        )

        self.assertEqual([label for label, _ in ordered], ["properties"])

    def test_missing_utils_module_is_skipped(self):
        real_import_module = importlib.import_module

        def fake_import_module(module_path):
            if module_path == "users.utils":
                raise ModuleNotFoundError(
                    "No module named 'users.utils'", name="users.utils"
                )
            return real_import_module(module_path)

        with mock.patch.object(
            ensure_command_module.importlib,
            "import_module",
            side_effect=fake_import_module,
        ):
            labels = [label for label, _, _ in self.command.discover_initializers()]

        self.assertNotIn("users", labels)

    def test_nested_import_error_inside_utils_module_propagates(self):
        real_import_module = importlib.import_module

        def fake_import_module(module_path):
            if module_path == "users.utils":
                raise ModuleNotFoundError(
                    "No module named 'gone_dependency'", name="gone_dependency"
                )
            return real_import_module(module_path)

        with mock.patch.object(
            ensure_command_module.importlib,
            "import_module",
            side_effect=fake_import_module,
        ):
            with self.assertRaises(ModuleNotFoundError):
                self.command.discover_initializers()


class InitializerTransactionTests(TestCase):
    def test_failed_initializer_rolls_back_earlier_changes(self):
        def first_initializer():
            Group.objects.create(name="rollback-marker")

        def failing_initializer():
            raise RuntimeError("initializer failed")

        initializers = [
            ("users", first_initializer, []),
            ("object_management", failing_initializer, ["users"]),
        ]
        with mock.patch.object(
            EnsureInitialDataCommand,
            "discover_initializers",
            return_value=initializers,
        ):
            with self.assertLogs(
                "brit.management.commands.ensure_initial_data", level="ERROR"
            ):
                with self.assertRaises(RuntimeError):
                    call_command(
                        "ensure_initial_data",
                        stdout=io.StringIO(),
                        stderr=io.StringIO(),
                    )

        self.assertFalse(Group.objects.filter(name="rollback-marker").exists())


class UsersInitialDataTests(TestCase):
    def test_new_admin_without_password_gets_unusable_password(self):
        with mock.patch.dict(os.environ, {"ADMIN_USERNAME": "fresh-admin"}, clear=True):
            ensure_users_data()

        admin = User.objects.get(username="fresh-admin")
        self.assertFalse(admin.has_usable_password())
        self.assertTrue(admin.password.startswith("!"))

    def test_new_admin_with_explicit_password_keeps_it_usable(self):
        with mock.patch.dict(
            os.environ,
            {"ADMIN_USERNAME": "pw-admin", "ADMIN_PASSWORD": "adm-secret"},
            clear=True,
        ):
            ensure_users_data()

        admin = User.objects.get(username="pw-admin")
        self.assertTrue(admin.has_usable_password())
        self.assertTrue(admin.check_password("adm-secret"))

    def test_existing_admin_password_and_flags_are_not_reset(self):
        admin = User.objects.create(
            username="keep-admin", is_superuser=True, is_staff=True
        )
        admin.set_password("original-secret")
        admin.save()

        with mock.patch.dict(
            os.environ,
            {"ADMIN_USERNAME": "keep-admin", "ADMIN_PASSWORD": "other-secret"},
            clear=True,
        ):
            ensure_users_data()

        admin.refresh_from_db()
        self.assertTrue(admin.check_password("original-secret"))
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_staff)


class FullInitialDataSeedingTests(TestCase):
    def _run_all_initializers(self, environment):
        with mock.patch.dict(os.environ, environment):
            call_command("ensure_initial_data", stdout=io.StringIO())

    @override_settings(DEFAULT_OBJECT_OWNER_USERNAME="bootstrap-owner")
    def test_full_initialization_with_distinct_owner_is_idempotent(self):
        environment = {
            "ADMIN_USERNAME": "bootstrap-admin",
            "ADMIN_PASSWORD": "adm-secret",
        }
        self._run_all_initializers(environment)

        admin = User.objects.get(username="bootstrap-admin")
        owner = User.objects.get(username="bootstrap-owner")
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password("adm-secret"))

        Unit.objects.get(owner=owner, name="No unit")

        months = TemporalDistribution.objects.get(
            owner=owner, name="Months of the year"
        )
        january = Timestep.objects.get(owner=owner, distribution=months, name="January")
        december = Timestep.objects.get(
            owner=owner, distribution=months, name="December"
        )
        Period.objects.get(
            distribution=months,
            first_timestep=january,
            last_timestep=december,
        )

        MaterialComponentGroup.objects.get(name="Total Material")
        MaterialComponent.objects.get(name="Fresh Matter (FM)")
        MaterialComponent.objects.get(name="Other")

        default_map = MapConfiguration.objects.get(name="Default Map Configuration")
        self.assertEqual(default_map.layers.count(), 3)

        frequency = CollectionFrequency.objects.get(
            name="Fixed; 52 per year (1 per week)"
        )
        CollectionSeason.objects.get(
            distribution=months,
            first_timestep=january,
            last_timestep=december,
        )
        CollectionCountOptions.objects.get(
            season__distribution=months, frequency=frequency, standard=52
        )

        category = MaterialCategory.objects.get(owner=owner, name="Biowaste component")
        self.assertEqual(category.publication_status, "published")

        self.assertFalse(Collection.objects.exists())
        self.assertFalse(GeoDataset.objects.exists())

        snapshot = {
            model: set(model.objects.values_list("pk", flat=True))
            for model in (
                User,
                Unit,
                TemporalDistribution,
                Timestep,
                Period,
                MaterialCategory,
                MapConfiguration,
                CollectionFrequency,
            )
        }

        default_map.layers.remove(default_map.layers.first())
        self._run_all_initializers(environment)

        self.assertEqual(default_map.layers.count(), 2)
        for model, primary_keys in snapshot.items():
            self.assertEqual(
                set(model.objects.values_list("pk", flat=True)), primary_keys
            )
        admin.refresh_from_db()
        self.assertTrue(admin.check_password("adm-secret"))

    @override_settings(DEFAULT_OBJECT_OWNER_USERNAME="defaults-owner")
    def test_full_initialization_seeds_point_property_and_product_category(self):
        environment = {
            "ADMIN_USERNAME": "defaults-admin",
            "ADMIN_PASSWORD": "adm-secret",
        }
        self._run_all_initializers(environment)

        owner = User.objects.get(username="defaults-owner")
        no_unit = Unit.objects.get(owner=owner, name="No unit")
        point_property = Property.objects.get(
            owner=owner, name="number of collection points"
        )
        self.assertEqual(point_property.publication_status, "published")
        self.assertEqual(list(point_property.allowed_units.all()), [no_unit])
        product = MaterialCategory.objects.get(owner=owner, name="Product")
        self.assertEqual(product.publication_status, "published")
        self.assertEqual(
            product.description,
            "A product is the output of a production process and is "
            "intentionally created from one or more materials to fulfil "
            "a specific function. It is a good with an intended positive "
            "market value.",
        )

    @override_settings(DEFAULT_OBJECT_OWNER_USERNAME="defaults-owner")
    def test_initializers_do_not_reuse_or_overwrite_existing_rows(self):
        environment = {
            "ADMIN_USERNAME": "defaults-admin",
            "ADMIN_PASSWORD": "adm-secret",
        }
        foreign = User.objects.create(username="foreign-owner")
        foreign_product = MaterialCategory.objects.create(
            owner=foreign,
            name="Product",
            description="foreign product description",
        )
        foreign_property = Property.objects.create(
            owner=foreign, name="number of collection points"
        )

        self._run_all_initializers(environment)

        owner = User.objects.get(username="defaults-owner")
        foreign_product.refresh_from_db()
        foreign_property.refresh_from_db()
        self.assertEqual(foreign_product.description, "foreign product description")
        self.assertEqual(
            MaterialCategory.objects.filter(owner=owner, name="Product").count(), 1
        )
        self.assertEqual(
            Property.objects.filter(
                owner=owner, name="number of collection points"
            ).count(),
            1,
        )

        product = MaterialCategory.objects.get(owner=owner, name="Product")
        point_property = Property.objects.get(
            owner=owner, name="number of collection points"
        )
        custom_unit = Unit.objects.create(owner=owner, name="custom unit")
        point_property.allowed_units.set([custom_unit])
        product.description = "custom product description"
        product.publication_status = "private"
        product.save()
        ids = (product.pk, point_property.pk, custom_unit.pk)

        self._run_all_initializers(environment)

        product.refresh_from_db()
        point_property.refresh_from_db()
        self.assertEqual(product.description, "custom product description")
        self.assertEqual(product.publication_status, "private")
        self.assertEqual(list(point_property.allowed_units.all()), [custom_unit])
        self.assertEqual(ids, (product.pk, point_property.pk, custom_unit.pk))

    @override_settings(DEFAULT_OBJECT_OWNER_USERNAME="defaults-owner")
    def test_initializers_tolerate_duplicate_matching_rows(self):
        environment = {
            "ADMIN_USERNAME": "defaults-admin",
            "ADMIN_PASSWORD": "adm-secret",
        }
        self._run_all_initializers(environment)

        owner = User.objects.get(username="defaults-owner")
        MaterialCategory.objects.create(
            owner=owner, name="Product", description="duplicate product"
        )
        Property.objects.create(owner=owner, name="number of collection points")

        self._run_all_initializers(environment)

        self.assertEqual(
            MaterialCategory.objects.filter(owner=owner, name="Product").count(), 2
        )
        self.assertEqual(
            Property.objects.filter(
                owner=owner, name="number of collection points"
            ).count(),
            2,
        )

    @override_settings(DEFAULT_OBJECT_OWNER_USERNAME="defaults-owner")
    def test_properties_initializer_keeps_no_unit_return_contract(self):
        User.objects.create(username="defaults-owner")

        result = ensure_properties_data()

        self.assertIn("no_unit", result)
        self.assertEqual(result["no_unit"].name, "No unit")

    def test_first_waste_component_after_initialization_gets_category(self):
        call_command("ensure_initial_data", stdout=io.StringIO())

        component = WasteComponent.objects.create(name="Garden waste")

        self.assertTrue(component.categories.filter(name="Biowaste component").exists())

    def test_waste_component_gets_default_owner_category(self):
        foreign_owner = User.objects.create(username="foreign-owner")
        foreign_category = MaterialCategory.objects.create(
            owner=foreign_owner,
            name="Biowaste component",
            publication_status="published",
        )
        component_owner = User.objects.create(username="component-owner")

        call_command("ensure_initial_data", stdout=io.StringIO())

        canonical = MaterialCategory.objects.get(
            owner=get_default_owner(), name="Biowaste component"
        )
        self.assertNotEqual(canonical.pk, foreign_category.pk)

        component = WasteComponent.objects.create(
            name="Garden waste", owner=component_owner
        )
        self.assertEqual(
            list(component.categories.values_list("pk", flat=True)),
            [canonical.pk],
        )

        call_command("ensure_initial_data", stdout=io.StringIO())
        self.assertEqual(
            MaterialCategory.objects.get(
                owner=get_default_owner(), name="Biowaste component"
            ).pk,
            canonical.pk,
        )

    def test_frequency_create_view_initializes_full_year_formset(self):
        call_command("ensure_initial_data", stdout=io.StringIO())
        creator = User.objects.create(username="creator", is_staff=True)
        self.client.force_login(creator)

        response = self.client.get(reverse("collectionfrequency-create"))

        self.assertEqual(response.status_code, 200)
        initial = response.context["formset"].initial[0]
        self.assertEqual(initial["first_timestep"].name, "January")
        self.assertEqual(initial["last_timestep"].name, "December")

    def test_frequency_form_uses_canonical_distribution_with_multiple_owners(self):
        call_command("ensure_initial_data", stdout=io.StringIO())
        other_owner = User.objects.create(username="other-owner")
        TemporalDistribution.objects.create(
            name="Months of the year", owner=other_owner
        )
        creator = User.objects.create(username="freq-creator", is_staff=True)
        self.client.force_login(creator)

        response = self.client.get(reverse("collectionfrequency-create"))

        self.assertEqual(response.status_code, 200)
        initial = response.context["formset"].initial[0]
        self.assertEqual(initial["first_timestep"].name, "January")
        self.assertEqual(initial["last_timestep"].name, "December")
        self.assertEqual(initial["distribution"].owner, get_default_owner())

    def test_public_pages_render_without_domain_data(self):
        call_command("ensure_initial_data", stdout=io.StringIO())

        for url_name in (
            "home",
            "sources-explorer",
            "wastecollection-explorer",
            "materials-explorer",
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)

    def test_maps_explorer_renders_without_domain_data(self):
        call_command("ensure_initial_data", stdout=io.StringIO())

        response = self.client.get("/maps/explorer/")

        self.assertEqual(response.status_code, 200)


class CookieConsentInitialDataTests(TestCase):
    def _run_brit_initializer(self):
        from brit.utils import ensure_initial_data

        ensure_initial_data()

    @override_settings(COOKIE_CONSENT_ENABLED=False)
    def test_disabled_consent_seeds_nothing(self):
        self._run_brit_initializer()

        self.assertFalse(CookieGroup.objects.exists())
        self.assertFalse(Cookie.objects.exists())

    @override_settings(COOKIE_CONSENT_ENABLED=True)
    def test_essential_cookies_seeded_without_analytics_key(self):
        with override_settings(GOOGLE_ANALYTICS_KEY=None):
            self._run_brit_initializer()

        essential = CookieGroup.objects.get(varname="essential")
        self.assertTrue(essential.is_required)
        cookie_names = set(essential.cookie_set.values_list("name", flat=True))
        self.assertIn(settings.SESSION_COOKIE_NAME, cookie_names)
        self.assertIn(settings.CSRF_COOKIE_NAME, cookie_names)
        for cookie in essential.cookie_set.all():
            self.assertEqual(cookie.domain, "")
        self.assertFalse(CookieGroup.objects.filter(varname="analytics").exists())

        self.assertEqual(self.client.get(reverse("home")).status_code, 200)
        self.assertEqual(self.client.get("/cookies/").status_code, 200)

    @override_settings(COOKIE_CONSENT_ENABLED=True, GOOGLE_ANALYTICS_KEY="G-TEST")
    def test_analytics_group_seeded_when_analytics_key_configured(self):
        self._run_brit_initializer()

        analytics = CookieGroup.objects.get(varname="analytics")
        self.assertFalse(analytics.is_required)
        self.assertTrue(analytics.cookie_set.filter(name="_ga").exists())

    @override_settings(COOKIE_CONSENT_ENABLED=True, GOOGLE_ANALYTICS_KEY="G-TEST")
    def test_second_run_preserves_existing_metadata_and_counts(self):
        self._run_brit_initializer()
        analytics = CookieGroup.objects.get(varname="analytics")
        analytics.description = "customized description"
        analytics.save()
        group_count = CookieGroup.objects.count()
        cookie_count = Cookie.objects.count()

        self._run_brit_initializer()

        analytics.refresh_from_db()
        self.assertEqual(analytics.description, "customized description")
        self.assertEqual(CookieGroup.objects.count(), group_count)
        self.assertEqual(Cookie.objects.count(), cookie_count)

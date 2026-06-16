from types import SimpleNamespace

from django.test import SimpleTestCase

from utils.object_management.review_hooks import (
    get_review_context_enrichments,
    get_review_search_fields,
    get_review_update_context,
    register_review_context_enricher,
    register_review_search_fields,
    register_review_update_context,
    restore_review_hooks_for_tests,
    snapshot_review_hooks_for_tests,
)


class ReviewHookRegistryTests(SimpleTestCase):
    def setUp(self):
        self.registry_snapshot = snapshot_review_hooks_for_tests()

    def tearDown(self):
        restore_review_hooks_for_tests(self.registry_snapshot)

    def test_context_enrichers_are_resolved_by_model_label(self):
        obj = SimpleNamespace(_meta=SimpleNamespace(app_label="demo", model_name="thing"))

        register_review_context_enricher(
            "demo.thing",
            lambda review_obj: {"plugin_label": review_obj._meta.model_name},
        )

        self.assertEqual(
            get_review_context_enrichments(obj),
            {"plugin_label": "thing"},
        )

    def test_search_fields_are_resolved_by_model_label(self):
        model = SimpleNamespace(
            _meta=SimpleNamespace(app_label="demo", model_name="thing")
        )

        register_review_search_fields("demo.thing", ["related__name"])

        self.assertEqual(
            get_review_search_fields(model),
            ("related__name",),
        )

    def test_update_context_hook_is_resolved_by_model_label(self):
        user = SimpleNamespace(id=1)
        obj = SimpleNamespace(_meta=SimpleNamespace(app_label="demo", model_name="thing"))

        register_review_update_context(
            "demo.thing",
            lambda review_user, review_obj: {
                "user_id": review_user.id,
                "model": review_obj._meta.model_name,
            },
        )

        self.assertEqual(
            get_review_update_context(user, obj),
            {"user_id": 1, "model": "thing"},
        )

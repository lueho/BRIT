"""Tests for utils.file_export.templatetags.file_export_tags."""

from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from ..templatetags.file_export_tags import export_link_modal, export_modal_button


class ExportLinkModalTagTestCase(SimpleTestCase):
    """Regression tests for the documented export_link_modal template tag."""

    def test_returns_modal_url_with_export_url_param(self):
        result = export_link_modal("export-modal")
        self.assertTrue(result.startswith(reverse("export-modal")))

    def test_extra_params_are_passed_through(self):
        result = export_link_modal("export-modal", list_type="private")
        self.assertIn("list_type=private", result)


class ExportModalButtonTagTestCase(SimpleTestCase):
    """Tests for the export_modal_button template tag."""

    def setUp(self):
        self.factory = RequestFactory()

    def _make_context(self, user=None):
        request = self.factory.get("/")
        request.user = user or MagicMock(is_authenticated=True)
        return {"request": request}

    def test_authenticated_user_gets_enabled_button(self):
        context = self._make_context()
        result = export_modal_button(context, "export-modal")
        self.assertFalse(result["export_disabled"])

    def test_anonymous_user_gets_disabled_button(self):
        context = self._make_context(user=AnonymousUser())
        result = export_modal_button(context, "export-modal")
        self.assertTrue(result["export_disabled"])

    def test_custom_text_is_passed_through(self):
        context = self._make_context()
        result = export_modal_button(context, "export-modal", text="Download")
        self.assertEqual(result["button_text"], "Download")

    def test_custom_element_id_is_passed_through(self):
        context = self._make_context()
        result = export_modal_button(context, "export-modal", element_id="my-btn")
        self.assertEqual(result["button_id"], "my-btn")

    def test_default_element_id_derived_from_url_name(self):
        context = self._make_context()
        result = export_modal_button(context, "export-modal")
        self.assertEqual(result["button_id"], "export-modal-export-modal")

    def test_extra_params_included_in_modal_href(self):
        context = self._make_context()
        result = export_modal_button(context, "export-modal", scope="public")
        self.assertIn("scope=public", result["modal_href"])

    def test_none_extra_param_excluded_from_top_level_modal_params(self):
        context = self._make_context()
        result = export_modal_button(context, "export-modal", empty_param=None)

        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(result["modal_href"])
        top_level_params = parse_qs(parsed.query)
        self.assertNotIn("empty_param", top_level_params)

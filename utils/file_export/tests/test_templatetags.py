from unittest.mock import MagicMock

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase

from ..templatetags.file_export_tags import export_link, export_modal_button

# Use 'export-modal' as the export_url_name: it exists and takes no args.


class ExportLinkTagTestCase(SimpleTestCase):
    """Tests for the export_link template tag."""

    def test_csv_format_returns_csv_icon_class(self):
        result = export_link("csv", "export-modal")
        self.assertIn("fa-file-csv", result["icon_class"])

    def test_xlsx_format_returns_excel_icon_class(self):
        result = export_link("xlsx", "export-modal")
        self.assertIn("fa-file-excel", result["icon_class"])

    def test_invalid_format_raises_value_error(self):
        with self.assertRaises(ValueError):
            export_link("pdf", "export-modal")

    def test_returns_correct_file_format(self):
        result = export_link("csv", "export-modal")
        self.assertEqual(result["file_format"], "csv")

    def test_progress_url_contains_placeholder(self):
        result = export_link("csv", "export-modal")
        self.assertIn("/progress/", result["progress_url"])


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
        # None params are filtered from the top-level modal query params
        # but still get encoded into the nested export_url query string.
        result = export_modal_button(context, "export-modal", empty_param=None)
        # The modal_href should not have empty_param=None as a top-level param
        # (it may appear inside the encoded export_url value)
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(result["modal_href"])
        top_level_params = parse_qs(parsed.query)
        self.assertNotIn("empty_param", top_level_params)

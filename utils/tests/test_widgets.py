from django.forms.widgets import HiddenInput
from django.test import TestCase

from ..widgets import (
    CreateEnabledTomSelectModelMultipleWidget,
    CreateEnabledTomSelectModelWidget,
    NullableRangeSliderWidget,
    RangeSliderWidget,
    SourceListWidget,
)


class CreateEnabledTomSelectWidgetTestCase(TestCase):
    def test_media_includes_ui_utils(self):
        """Inline-create error reporting falls back to ``showInlineAlert``
        from ``js/ui_utils.min.js``, so the widget must ship it."""
        for widget_class in (
            CreateEnabledTomSelectModelWidget,
            CreateEnabledTomSelectModelMultipleWidget,
        ):
            media = str(widget_class().media)
            self.assertIn("js/ui_utils.min.js", media)


class RangeSliderWidgetTestCase(TestCase):
    def test_init(self):
        widget = RangeSliderWidget()
        self.assertIsInstance(widget.widgets[0], HiddenInput)
        self.assertIsInstance(widget.widgets[1], HiddenInput)

    def test_decompress(self):
        widget = RangeSliderWidget()
        self.assertEqual(widget.decompress(slice(50, 100)), [50, 100])

    def test_get_context(self):
        widget = RangeSliderWidget(attrs={"data-range_min": 0, "data-range_max": 100})
        context = widget.get_context("test_widget", [50, 100], None)
        self.assertEqual(context["widget"]["attrs"]["data-cur_min"], 50)
        self.assertEqual(context["widget"]["attrs"]["data-cur_max"], 100)
        self.assertEqual(context["widget"]["value_text"], "50 - 100")

    def test_widget_get_context_with_none_values(self):
        widget = RangeSliderWidget(attrs={"data-range_min": 0, "data-range_max": 100})
        context = widget.get_context("test_widget", None, None)
        self.assertEqual(context["widget"]["attrs"]["data-cur_min"], 0)
        self.assertEqual(context["widget"]["attrs"]["data-cur_max"], 100)
        self.assertEqual(context["widget"]["value_text"], "0 - 100")

    def test_widget_get_context_with_subwidgets_ids(self):
        widget = RangeSliderWidget(attrs={"data-range_min": 0, "data-range_max": 100})
        context = widget.get_context("test_widget", [50, 100], None)
        base_id = context["widget"]["name"]
        for swx, subwidget in enumerate(context["widget"]["subwidgets"]):
            self.assertEqual(
                subwidget["attrs"]["id"], base_id + "_" + widget.suffixes[swx]
            )

    def test_widget_get_context_with_unit_in_value_text(self):
        widget = RangeSliderWidget(
            attrs={"data-range_min": 0, "data-range_max": 100, "data-unit": "m"}
        )
        context = widget.get_context("test_widget", [50, 100], None)
        self.assertEqual(context["widget"]["value_text"], "50m - 100m")


class NullableRangeSliderWidgetTestCase(TestCase):
    def test_init(self):
        widget = NullableRangeSliderWidget(
            attrs={"data-range_min": 0, "data-range_max": 100, "data-is_null": "true"}
        )
        self.assertEqual(len(widget.widgets), 3)

    def test_decompress(self):
        widget = NullableRangeSliderWidget()
        decompressed = widget.decompress(None)
        self.assertEqual(decompressed, [None, None, "true"])

    def test_get_context(self):
        widget = NullableRangeSliderWidget(
            attrs={"data-range_min": 0, "data-range_max": 100, "data-is_null": "true"}
        )
        context = widget.get_context("nullable_range_slider", [0, 100, "true"], None)
        self.assertEqual(context["widget"]["attrs"]["data-cur_min"], 0)
        self.assertEqual(context["widget"]["attrs"]["data-cur_max"], 100)
        self.assertEqual(context["widget"]["attrs"]["data-cur_is_null"], "true")


class SourceListWidgetTestCase(TestCase):
    def test_media_includes_tomselect_library(self):
        """The widget must ship the TomSelect library itself.

        ``source_list_widget.js`` calls ``new TomSelect(...)``, which is only
        defined by ``django-tomselect.js``. On forms without another
        django_tomselect widget (e.g. AnalyticalMethodModelForm) the library
        was never loaded, so widget initialisation died on a ReferenceError
        and neither the search input nor the "Add source" button worked.
        """
        media = str(SourceListWidget().media)
        self.assertIn("django_tomselect/js/django-tomselect", media)
        self.assertIn("utils/js/source_list_widget.js", media)
        self.assertIn("vendor/tom-select/css/tom-select", media)

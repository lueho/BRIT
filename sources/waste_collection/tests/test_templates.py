from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.test import SimpleTestCase


class OrphanedTemplatesRemovedTests(SimpleTestCase):
    def test_unreferenced_templates_are_not_resolvable(self):
        for template_name in (
            "collection_review_filter.html",
            "waste_collection_popup.html",
        ):
            with self.subTest(template_name=template_name):
                with self.assertRaises(TemplateDoesNotExist):
                    get_template(template_name)

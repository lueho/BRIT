from django.forms.models import inlineformset_factory
from django.test import TestCase

from sources.waste_collection.models import WasteFlyer

from ..forms import SourceAuthorFormSet, SourceModelForm
from ..models import Source, SourceAuthor


class SourceAuthorFormSetRegressionTestCase(TestCase):
    """Regression tests for SourceAuthorFormSet edge cases."""

    def test_normalize_positions_skips_unsaved_wasteflyer_instance(self):
        """It should not access reverse relations before the parent instance is saved."""
        source_author_formset_class = inlineformset_factory(
            Source,
            SourceAuthor,
            formset=SourceAuthorFormSet,
            fields=("author",),
            extra=0,
            can_delete=True,
        )
        formset = source_author_formset_class(instance=WasteFlyer())

        formset._normalize_positions()


class SourceModelFormTestCase(TestCase):
    def test_form_exposes_article_metadata_fields(self):
        form = SourceModelForm()

        self.assertIn("volume", form.fields)
        self.assertIn("eid", form.fields)
        self.assertIn("number", form.fields)
        self.assertIn("pages", form.fields)
        self.assertIn("month", form.fields)

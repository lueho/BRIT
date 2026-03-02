from django.forms.models import inlineformset_factory
from django.test import TestCase

from case_studies.soilcom.models import WasteFlyer

from ..forms import SourceAuthorFormSet
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

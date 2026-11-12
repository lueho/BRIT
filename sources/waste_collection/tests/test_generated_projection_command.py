"""User-facing help for source-bound collection projection maintenance."""

from django.test import SimpleTestCase

from sources.waste_collection.management.commands.backfill_derived_cpv import Command


class GeneratedProjectionCommandHelpTests(SimpleTestCase):
    def test_help_distinguishes_source_authority_from_compatibility_metadata(self):
        parser = Command().create_parser("manage.py", "backfill_derived_cpv")
        help_text = " ".join(parser.format_help().split())
        for expected in (
            "source-linked",
            "read-only",
            "compatibility metadata",
            "does not grant access",
            "does not publish or approve evidence",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, help_text)

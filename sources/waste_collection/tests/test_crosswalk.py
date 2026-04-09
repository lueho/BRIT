"""Tests for Soilcom raw-term crosswalk preprocessing."""

import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from sources.waste_collection.crosswalk import (
    CrosswalkValidationError,
    apply_crosswalks_to_record,
    ensure_crosswalk_mappings_valid,
    get_crosswalk_equivalences,
    validate_crosswalk_mappings,
    validate_record_against_controlled_vocabulary,
)
from sources.waste_collection.vocabulary import SEMANTIC_CONTRACT, get_concepts_by_uri


class CrosswalkPreprocessingTestCase(SimpleTestCase):
    """Verify harmonization mapping before importer lookup resolution."""

    def _write_crosswalk_validation_fixture(
        self,
        root: Path,
        csv_rows: list[str],
        ttl_body: str,
    ) -> tuple[Path, Path]:
        mappings_dir = root / "mappings"
        mappings_dir.mkdir()
        (mappings_dir / "fixture.csv").write_text(
            "\n".join(
                [
                    "domain,source_term,source_language,target_scheme_uri,target_concept_uri,target_label,notes",
                    *csv_rows,
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        ttl_path = root / "vocabulary.ttl"
        ttl_path.write_text(ttl_body, encoding="utf-8")
        return mappings_dir, ttl_path

    def test_maps_sweden_terms_to_canonical_labels(self):
        """Swedish raw terms should map to canonical controlled-vocabulary labels."""
        record = {
            "collection_system": "Ingen utsortering",
            "sorting_method": "Optisk sortering",
            "connection_type": "Obl",
            "fee_system": "PAYT",
        }

        mapped = apply_crosswalks_to_record(record)

        self.assertEqual(mapped["collection_system"], "No separate collection")
        self.assertEqual(mapped["sorting_method"], "Optical bag sorting")
        self.assertEqual(mapped["connection_type"], "mandatory")
        self.assertEqual(mapped["fee_system"], "Pay as you throw (PAYT)")

    def test_maps_brandenburg_category_terms(self):
        """German Brandenburg waste categories should map to canonical labels."""
        record = {
            "waste_category": "Restabfall/Hausmüll",
            "collection_system": "Bring point",
        }

        mapped = apply_crosswalks_to_record(record)

        self.assertEqual(mapped["waste_category"], "Residual waste")
        self.assertEqual(mapped["collection_system"], "Bring point")

    def test_maps_german_equivalent_terms_to_same_canonical_label(self):
        """Restabfall, Restmüll, and Hausmüll should normalize to one concept label."""
        for source_term in ["Restabfall", "Restmüll", "Hausmüll", "Hausmuell"]:
            with self.subTest(source_term=source_term):
                mapped = apply_crosswalks_to_record({"waste_category": source_term})
                self.assertEqual(mapped["waste_category"], "Residual waste")

    def test_maps_country_pack_terms_to_canonical_labels(self):
        """Country-pack NL/DK/BE/UK terms should normalize to canonical labels."""
        record = {
            "waste_category": "Restafval",
            "collection_system": "Kerbside collection",
            "sorting_method": "Kildesortering",
            "fee_system": "DIFTAR",
            "connection_type": "Obligatoire",
            "required_bin_capacity_reference": "Per indbygger",
        }

        mapped = apply_crosswalks_to_record(record)

        self.assertEqual(mapped["waste_category"], "Residual waste")
        self.assertEqual(mapped["collection_system"], "Door to door")
        self.assertEqual(mapped["sorting_method"], "Separate bins")
        self.assertEqual(mapped["fee_system"], "Pay as you throw (PAYT)")
        self.assertEqual(mapped["connection_type"], "mandatory")
        self.assertEqual(mapped["required_bin_capacity_reference"], "person")

    def test_exposes_equivalences_by_canonical_concept_uri(self):
        """Equivalent source terms should be grouped by stable concept URI."""
        equivalences = get_crosswalk_equivalences()

        concept_uri = (
            "https://brit.bioresource-tools.net/vocab/soilcom/"
            "concept/waste-category/residual-waste"
        )
        waste_category_equivalences = equivalences["waste_category"][concept_uri]

        self.assertEqual(
            waste_category_equivalences["target_label"],
            "Residual waste",
        )
        terms = {
            (entry["language"], entry["term"])
            for entry in waste_category_equivalences["source_terms"]
        }
        self.assertIn(("de", "Restabfall"), terms)
        self.assertIn(("de", "Restmüll"), terms)
        self.assertIn(("de", "Hausmüll"), terms)

    def test_equivalences_include_multicountry_terms_for_residual_waste(self):
        """Residual waste concept should include equivalent terms from multiple countries."""
        equivalences = get_crosswalk_equivalences()

        concept_uri = (
            "https://brit.bioresource-tools.net/vocab/soilcom/"
            "concept/waste-category/residual-waste"
        )
        terms = {
            (entry["language"], entry["term"])
            for entry in equivalences["waste_category"][concept_uri]["source_terms"]
        }

        self.assertIn(("de", "Restabfall"), terms)
        self.assertIn(("nl", "Restafval"), terms)
        self.assertIn(("fr", "Dechets residuels"), terms)
        self.assertIn(("en", "General waste"), terms)

    def test_keeps_unknown_terms_unchanged(self):
        """Unknown terms should pass through unchanged for downstream handling."""
        record = {
            "sorting_method": "Custom local method",
            "fee_system": "Other",
        }

        mapped = apply_crosswalks_to_record(record)

        self.assertEqual(mapped["sorting_method"], "Custom local method")
        self.assertEqual(mapped["fee_system"], "Other")

    def test_controlled_vocabulary_validation_reports_unknown_values(self):
        """Validation should report values outside the controlled vocabulary."""
        vocabulary = {
            "collection_systems": ["Door to door"],
            "collection_frequencies": ["Fixed; 26 per year (1 per 2 weeks)"],
            "waste_categories": ["Food waste"],
            "sorting_methods": ["Separate bins"],
            "fee_systems": ["Flat fee"],
            "materials": ["Food waste: Processed plant-based"],
            "connection_types": [{"label": "mandatory"}],
            "required_bin_capacity_references": [{"value": "person"}],
        }
        record = {
            "collection_system": "Unknown",
            "frequency": "Seasonal special",
            "waste_category": "Food waste",
            "sorting_method": "Other",
            "fee_system": "Flat fee",
            "allowed_materials": ["Food waste: Processed plant-based", "Unknown item"],
            "connection_type": "VOLUNTARY",
            "required_bin_capacity_reference": "household",
        }

        warnings = validate_record_against_controlled_vocabulary(record, vocabulary)

        self.assertTrue(
            any("collection_system" in warning for warning in warnings),
        )
        self.assertTrue(any("frequency" in warning for warning in warnings))
        self.assertTrue(any("sorting_method" in warning for warning in warnings))
        self.assertTrue(any("allowed_materials" in warning for warning in warnings))
        self.assertTrue(any("connection_type" in warning for warning in warnings))
        self.assertTrue(
            any("required_bin_capacity_reference" in warning for warning in warnings),
        )

    def test_controlled_vocabulary_validation_accepts_known_values(self):
        """Validation should return no warnings for known controlled values."""
        vocabulary = {
            "collection_systems": ["No separate collection"],
            "collection_frequencies": ["Fixed; 26 per year (1 per 2 weeks)"],
            "waste_categories": ["Residual waste"],
            "sorting_methods": ["Optical bag sorting"],
            "fee_systems": ["Pay as you throw (PAYT)"],
            "materials": ["Food waste: Processed plant-based"],
            "connection_types": [{"label": "mandatory"}],
            "required_bin_capacity_references": [{"value": "person"}],
        }
        record = {
            "collection_system": "No separate collection",
            "frequency": "Fixed; 26 per year (1 per 2 weeks)",
            "waste_category": "Residual waste",
            "sorting_method": "Optical bag sorting",
            "fee_system": "Pay as you throw (PAYT)",
            "allowed_materials": ["Food waste: Processed plant-based"],
            "forbidden_materials": ["Food waste: Processed plant-based"],
            "connection_type": "mandatory",
            "required_bin_capacity_reference": "person",
        }

        warnings = validate_record_against_controlled_vocabulary(record, vocabulary)

        self.assertEqual(warnings, [])

    def test_controlled_vocabulary_validation_accepts_connection_type_import_aliases(
        self,
    ):
        """Importer-supported connection_type aliases should not emit false warnings."""
        vocabulary = {
            "connection_types": [
                {
                    "value": "MANDATORY_WITH_HOME_COMPOSTER_EXCEPTION",
                    "label": "mandatory with exception for home composters",
                }
            ]
        }

        warnings = validate_record_against_controlled_vocabulary(
            {"connection_type": "Mandatory with exception"},
            vocabulary,
        )

        self.assertEqual(warnings, [])

    def test_controlled_vocabulary_validation_accepts_bin_capacity_import_aliases(self):
        """Importer-supported required-bin-capacity aliases should not emit false warnings."""
        vocabulary = {
            "required_bin_capacity_references": [{"value": "person"}],
        }

        warnings = validate_record_against_controlled_vocabulary(
            {"required_bin_capacity_reference": "Inh. & month"},
            vocabulary,
        )

        self.assertEqual(warnings, [])

    def test_crosswalk_uri_validation_accepts_valid_rows(self):
        """Crosswalk URI validation should accept rows consistent with the vocabulary."""
        vocabulary = {
            "uri_base": "https://example.org/vocab/soilcom",
            "concept_schemes": {
                "waste_categories": (
                    "https://example.org/vocab/soilcom/scheme/waste-category"
                ),
                "required_bin_capacity_references": (
                    "https://example.org/vocab/soilcom/scheme/required-bin-capacity-reference"
                ),
            },
        }
        ttl_body = "\n".join(
            [
                "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
                "@prefix britvoc: <https://example.org/vocab/soilcom/> .",
                "",
                "britvoc:concept/waste-category/residual-waste a skos:Concept ;",
                "    skos:inScheme britvoc:scheme/waste-category ;",
                '    skos:prefLabel "Residual waste"@en .',
                "",
                "britvoc:concept/required-bin-capacity-reference/person a skos:Concept ;",
                "    skos:inScheme britvoc:scheme/required-bin-capacity-reference ;",
                '    skos:prefLabel "per person"@en ;',
                '    skos:notation "person" .',
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            mappings_dir, ttl_path = self._write_crosswalk_validation_fixture(
                Path(temp_dir),
                [
                    "waste_category,Residual,de,https://example.org/vocab/soilcom/scheme/waste-category,https://example.org/vocab/soilcom/concept/waste-category/residual-waste,Residual waste,",
                    "required_bin_capacity_reference,Per inwoner,nl,https://example.org/vocab/soilcom/scheme/required-bin-capacity-reference,https://example.org/vocab/soilcom/concept/required-bin-capacity-reference/person,person,",
                ],
                ttl_body,
            )

            errors = validate_crosswalk_mappings(
                vocabulary_snapshot=vocabulary,
                mappings_dir=mappings_dir,
                vocabulary_ttl_path=ttl_path,
            )

        self.assertEqual(errors, [])

    def test_get_concepts_by_uri_reads_canonical_scheme_and_label_metadata(self):
        """Vocabulary helper should expose canonical concept metadata keyed by URI."""
        ttl_body = "\n".join(
            [
                "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
                "@prefix britvoc: <https://brit.bioresource-tools.net/vocab/soilcom/> .",
                "",
                "britvoc:concept/required-bin-capacity-reference/person a skos:Concept ;",
                "    skos:inScheme britvoc:scheme/required-bin-capacity-reference ;",
                '    skos:prefLabel "per person"@en ;',
                '    skos:notation "person" .',
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            ttl_path = Path(temp_dir) / "vocabulary.ttl"
            ttl_path.write_text(ttl_body, encoding="utf-8")

            concepts_by_uri = get_concepts_by_uri(vocabulary_ttl_path=ttl_path)

        self.assertEqual(
            concepts_by_uri[
                "https://brit.bioresource-tools.net/vocab/soilcom/concept/required-bin-capacity-reference/person"
            ],
            {
                "scheme_uri": (
                    "https://brit.bioresource-tools.net/vocab/soilcom/"
                    "scheme/required-bin-capacity-reference"
                ),
                "label": "per person",
                "notation": "person",
            },
        )

    @patch("sources.waste_collection.crosswalk.get_ttl_concept_registry")
    def test_crosswalk_uri_validation_uses_snapshot_concepts_by_uri_when_present(
        self,
        mock_get_registry,
    ):
        """Crosswalk validation should reuse the snapshot concept registry when available."""
        vocabulary = {
            "uri_base": "https://example.org/vocab/soilcom",
            "concept_schemes": {
                "waste_categories": (
                    "https://example.org/vocab/soilcom/scheme/waste-category"
                ),
            },
            "concepts_by_uri": {
                "https://example.org/vocab/soilcom/concept/waste-category/residual-waste": {
                    "scheme_uri": (
                        "https://example.org/vocab/soilcom/scheme/waste-category"
                    ),
                    "label": "Residual waste",
                    "notation": None,
                }
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            mappings_dir, ttl_path = self._write_crosswalk_validation_fixture(
                Path(temp_dir),
                [
                    "waste_category,Residual,de,https://example.org/vocab/soilcom/scheme/waste-category,https://example.org/vocab/soilcom/concept/waste-category/residual-waste,Residual waste,",
                ],
                "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n",
            )

            errors = validate_crosswalk_mappings(
                vocabulary_snapshot=vocabulary,
                mappings_dir=mappings_dir,
                vocabulary_ttl_path=ttl_path,
            )

        self.assertEqual(errors, [])
        mock_get_registry.assert_not_called()

    def test_crosswalk_uri_validation_reports_wrong_scheme_and_label(self):
        """Crosswalk URI validation should report scheme and target-label mismatches."""
        vocabulary = {
            "uri_base": "https://example.org/vocab/soilcom",
            "concept_schemes": {
                "waste_categories": (
                    "https://example.org/vocab/soilcom/scheme/waste-category"
                ),
            },
        }
        ttl_body = "\n".join(
            [
                "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
                "@prefix britvoc: <https://example.org/vocab/soilcom/> .",
                "",
                "britvoc:concept/waste-category/residual-waste a skos:Concept ;",
                "    skos:inScheme britvoc:scheme/waste-category ;",
                '    skos:prefLabel "Residual waste"@en .',
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            mappings_dir, ttl_path = self._write_crosswalk_validation_fixture(
                Path(temp_dir),
                [
                    "waste_category,Residual,de,https://example.org/vocab/soilcom/scheme/fee-system,https://example.org/vocab/soilcom/concept/waste-category/residual-waste,General waste,",
                ],
                ttl_body,
            )

            errors = validate_crosswalk_mappings(
                vocabulary_snapshot=vocabulary,
                mappings_dir=mappings_dir,
                vocabulary_ttl_path=ttl_path,
            )

        self.assertTrue(any("must target scheme" in error for error in errors))
        self.assertTrue(any("target_label" in error for error in errors))

    def test_crosswalk_uri_validation_reports_conflicting_duplicate_source_terms(self):
        """Conflicting mappings for the same normalized source term should fail validation."""
        vocabulary = {
            "uri_base": "https://example.org/vocab/soilcom",
            "concept_schemes": {
                "waste_categories": (
                    "https://example.org/vocab/soilcom/scheme/waste-category"
                ),
            },
        }
        ttl_body = "\n".join(
            [
                "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .",
                "@prefix britvoc: <https://example.org/vocab/soilcom/> .",
                "",
                "britvoc:concept/waste-category/residual-waste a skos:Concept ;",
                "    skos:inScheme britvoc:scheme/waste-category ;",
                '    skos:prefLabel "Residual waste"@en .',
                "",
                "britvoc:concept/waste-category/biowaste a skos:Concept ;",
                "    skos:inScheme britvoc:scheme/waste-category ;",
                '    skos:prefLabel "Biowaste"@en .',
            ]
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            mappings_dir, ttl_path = self._write_crosswalk_validation_fixture(
                Path(temp_dir),
                [
                    "waste_category,Restafval,nl,https://example.org/vocab/soilcom/scheme/waste-category,https://example.org/vocab/soilcom/concept/waste-category/residual-waste,Residual waste,",
                    "waste_category,restafval,en,https://example.org/vocab/soilcom/scheme/waste-category,https://example.org/vocab/soilcom/concept/waste-category/biowaste,Biowaste,",
                ],
                ttl_body,
            )

            with self.assertRaises(CrosswalkValidationError):
                ensure_crosswalk_mappings_valid(
                    vocabulary_snapshot=vocabulary,
                    mappings_dir=mappings_dir,
                    vocabulary_ttl_path=ttl_path,
                )

    def test_semantic_contract_requires_uri_matching(self):
        """Semantic contract must enforce URI-first matching for harmonization."""
        self.assertEqual(
            SEMANTIC_CONTRACT["canonical_identifier_field"],
            "target_concept_uri",
        )
        self.assertTrue(
            SEMANTIC_CONTRACT["equivalence_policy"][
                "agent_matching_must_use_concept_uri"
            ],
        )


class ValidateWasteCollectionCrosswalksCommandTestCase(SimpleTestCase):
    """Verify the waste_collection crosswalk validation management command."""

    @patch(
        "sources.waste_collection.management.commands.validate_waste_collection_crosswalks.validate_crosswalk_mappings"
    )
    def test_command_succeeds_when_crosswalk_assets_are_valid(self, mock_validate):
        """Command should emit success output when no crosswalk errors are found."""
        mock_validate.return_value = []
        stdout = StringIO()

        call_command("validate_waste_collection_crosswalks", stdout=stdout)

        self.assertIn(
            "Waste collection crosswalk validation passed.", stdout.getvalue()
        )

    @patch(
        "sources.waste_collection.management.commands.validate_waste_collection_crosswalks.validate_crosswalk_mappings"
    )
    def test_command_raises_command_error_when_crosswalk_assets_are_invalid(
        self,
        mock_validate,
    ):
        """Command should fail with the underlying validation errors for CI visibility."""
        mock_validate.return_value = [
            "fixture.csv:2: Unknown target_concept_uri 'https://example.org/bad'."
        ]

        with self.assertRaisesMessage(
            CommandError,
            "fixture.csv:2: Unknown target_concept_uri 'https://example.org/bad'.",
        ):
            call_command("validate_waste_collection_crosswalks")

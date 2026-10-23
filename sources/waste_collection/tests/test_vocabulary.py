"""Tests for the published waste collection vocabulary version contract."""

import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from sources.waste_collection.vocabulary import (
    VOCABULARY_URI_BASE,
    VOCABULARY_VERSION,
    get_concepts_by_uri,
)

ONTOLOGY_DIR = Path(__file__).resolve().parents[1] / "ontology"
EXPORT_PATH = ONTOLOGY_DIR / "export" / "controlled_vocabulary.json"
VOCABULARY_TTL_PATH = ONTOLOGY_DIR / "vocabulary.ttl"

RELEASED_PREF_LABELS = {
    "0.4.0": {
        f"{VOCABULARY_URI_BASE}/concept/unit/kg-per-cap-a": "kg/(cap.*a)",
    },
}


class VocabularyVersionTestCase(SimpleTestCase):
    def test_turtle_version_matches_vocabulary_version(self):
        text = VOCABULARY_TTL_PATH.read_text(encoding="utf-8")
        match = re.search(r'owl:versionInfo "([^"]+)"', text)

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), VOCABULARY_VERSION)

    def test_exported_snapshot_matches_vocabulary(self):
        snapshot = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))

        self.assertEqual(snapshot["version"], VOCABULARY_VERSION)
        self.assertEqual(snapshot["concepts_by_uri"], get_concepts_by_uri())

    def test_released_version_keeps_its_labels(self):
        concepts = get_concepts_by_uri()

        for version, labels in RELEASED_PREF_LABELS.items():
            if version != VOCABULARY_VERSION:
                continue
            for uri, label in labels.items():
                with self.subTest(version=version, uri=uri):
                    self.assertEqual(concepts[uri]["label"], label)

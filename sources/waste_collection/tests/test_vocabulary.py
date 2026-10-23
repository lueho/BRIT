"""Tests for the published waste collection vocabulary version contract."""

import hashlib
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from sources.waste_collection.vocabulary import (
    VOCABULARY_VERSION,
    get_concepts_by_uri,
)

ONTOLOGY_DIR = Path(__file__).resolve().parents[1] / "ontology"
EXPORT_PATH = ONTOLOGY_DIR / "export" / "controlled_vocabulary.json"
VOCABULARY_TTL_PATH = ONTOLOGY_DIR / "vocabulary.ttl"

# SHA-256 of the sorted-JSON ``get_concepts_by_uri()`` registry per released
# version. Changing any concept requires a version bump and a new entry.
RELEASED_CONCEPT_FINGERPRINTS = {
    "0.4.0": "03c6829e68cd7e635a65a1060b27267da40363f3961e1bdd90d13273e309f2a2",
    "0.4.1": "86abd9d7599d229ba8e5a989057cd2fc2d360f73324ff3da4c2b4f0e6fa60880",
}


def _concept_fingerprint(concepts):
    return hashlib.sha256(json.dumps(concepts, sort_keys=True).encode()).hexdigest()


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

    def test_concepts_match_fingerprint_of_current_version(self):
        self.assertIn(VOCABULARY_VERSION, RELEASED_CONCEPT_FINGERPRINTS)
        self.assertEqual(
            _concept_fingerprint(get_concepts_by_uri()),
            RELEASED_CONCEPT_FINGERPRINTS[VOCABULARY_VERSION],
        )

    def test_released_versions_have_distinct_fingerprints(self):
        fingerprints = list(RELEASED_CONCEPT_FINGERPRINTS.values())

        self.assertEqual(len(fingerprints), len(set(fingerprints)))

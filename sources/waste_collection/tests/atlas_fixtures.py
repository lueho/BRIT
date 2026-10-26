"""Test-only Waste Atlas fixture helpers.

The ``WasteAtlasMapConfiguration`` seed migrations were squashed into
``0001_squashed_0027`` and the individual migration modules removed, so
the previous replay-based fixture is obsolete: every migrated test
database already carries the seeded rows and their amendments.  The
helper is kept as a guarded no-op for the existing call sites.
"""

from django.apps import apps


def seed_atlas_map_configurations():
    apps.get_model("waste_atlas", "WasteAtlasMapConfiguration")
    return

import json
from pathlib import Path

from .models import WasteAtlasMapConfiguration, WasteAtlasRenderingSettings


def ensure_initial_data(stdout=None):
    """
    Ensures the default Waste Atlas map configurations and the rendering
    settings singleton exist. Idempotent: existing rows, including customized
    configurations, are never modified.
    """
    defaults_path = Path(__file__).with_name("initial_map_configurations.json")
    configurations = json.loads(defaults_path.read_text())
    for key, configuration in configurations.items():
        WasteAtlasMapConfiguration.objects.get_or_create(
            key=key, defaults={"configuration": configuration}
        )
    WasteAtlasRenderingSettings.objects.get_or_create(
        pk=WasteAtlasRenderingSettings.SINGLETON_PK
    )
    if stdout:
        print(
            f"Ensured {len(configurations)} Waste Atlas map configurations.",
            file=stdout,
        )

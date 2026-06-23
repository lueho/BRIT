import ast
from pathlib import Path

from django.test import SimpleTestCase


class MapsLayeringTests(SimpleTestCase):
    def test_maps_does_not_import_source_registry(self):
        maps_dir = Path(__file__).resolve().parent.parent
        offenders = []

        for path in maps_dir.rglob("*.py"):
            relative_path = path.relative_to(maps_dir)
            if relative_path.parts[0] in {"migrations", "tests"}:
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "sources.registry"
                ):
                    offenders.append(str(relative_path))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "sources.registry":
                            offenders.append(str(relative_path))

        self.assertEqual(
            offenders,
            [],
            "maps modules must consume maps-owned registries, not sources.registry",
        )

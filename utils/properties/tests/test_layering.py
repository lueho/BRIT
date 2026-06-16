import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class PropertiesLayeringTests(SimpleTestCase):
    def test_properties_and_shared_forms_do_not_import_bibliography(self):
        checked_paths = [
            Path("utils/properties/models.py"),
            Path("utils/properties/serializers.py"),
            Path("utils/forms.py"),
        ]

        for relative_path in checked_paths:
            with self.subTest(path=str(relative_path)):
                tree = ast.parse((settings.BASE_DIR / relative_path).read_text())
                imported_modules = {
                    module
                    for node in ast.walk(tree)
                    for module in _imported_modules(node)
                }

                self.assertNotIn("bibliography", imported_modules)


def _imported_modules(node):
    if isinstance(node, ast.Import):
        return [alias.name.split(".", maxsplit=1)[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and node.module:
        return [node.module.split(".", maxsplit=1)[0]]
    return []

import ast
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class LayeringContract:
    layers: Mapping[str, int]
    allowed_upward_imports: set[tuple[str, str]] = field(default_factory=set)
    ignored_path_parts: set[str] = field(
        default_factory=lambda: {"migrations", "tests", "__pycache__"}
    )


def find_layering_violations(
    repo_root: Path,
    contract: LayeringContract,
) -> list[str]:
    violations: list[str] = []

    for path in sorted(repo_root.rglob("*.py")):
        relative_path = path.relative_to(repo_root)
        if _should_ignore_path(relative_path, contract):
            continue

        importer = relative_path.parts[0]
        importer_layer = contract.layers.get(importer)
        if importer_layer is None:
            continue

        tree = ast.parse(path.read_text(), filename=str(path))
        for imported_module, line_number in _iter_imports(tree):
            imported_root = imported_module.split(".", 1)[0]
            imported_layer = contract.layers.get(imported_root)
            if imported_layer is None or imported_layer <= importer_layer:
                continue
            if (str(relative_path), imported_module) in contract.allowed_upward_imports:
                continue
            violations.append(
                f"{relative_path}:{line_number} imports {imported_module} "
                f"(L{importer_layer} {importer} -> "
                f"L{imported_layer} {imported_root})"
            )

    return violations


def _should_ignore_path(relative_path: Path, contract: LayeringContract) -> bool:
    return any(part in contract.ignored_path_parts for part in relative_path.parts)


def _iter_imports(tree: ast.AST) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.append((node.module, node.lineno))

    return imports

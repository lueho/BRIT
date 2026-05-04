from importlib import import_module

from sources.contracts import SourceDomainExport
from sources.registry import get_source_domain_plugins
from utils.file_export.export_registry import register_export


def _discover_source_domain_exports() -> tuple[SourceDomainExport, ...]:
    exports: list[SourceDomainExport] = []

    for plugin in get_source_domain_plugins():
        if "exports" not in plugin.capabilities:
            continue

        module_name = f"{plugin.get_app_module()}.exports"
        try:
            exports_module = import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                continue
            raise

        module_exports = getattr(exports_module, "EXPORTS", ())
        for export in module_exports:
            if not isinstance(export, SourceDomainExport):
                raise TypeError(
                    f"{module_name}.EXPORTS entries must be SourceDomainExport instances"
                )
            exports.append(export)

    return tuple(exports)


for export in _discover_source_domain_exports():
    register_export(
        export.model_label,
        export.filterset,
        export.serializer,
        export.renderers,
    )

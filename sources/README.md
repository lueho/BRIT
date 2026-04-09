# Sources hub and domain plugin contract

The `sources` package is the hub for BRIT source-domain applications.
Each domain package remains a normal Django app, but it should also publish a minimal plugin descriptor so the hub can discover it explicitly.
Core code in `sources` should not import built-in domain apps directly. Integration should happen through installed-app discovery and the shared plugin contract.

## Required files for a source-domain plugin

- `apps.py`
- `models.py`
- `admin.py`
- `urls.py`
- `plugin.py`
- `tests/`

## `plugin.py` contract

Each domain app should expose a module-level `plugin` value of type `SourceDomainPlugin`.
The descriptor currently declares:

- `slug`
- `verbose_name`
- `app_config`
- `urlconf`
- `capabilities`
- `mount_in_hub`
- `mount_path`
- `explorer_context_var`
- `published_count_getter`

`app_config` is also used to derive the app module path for optional plugin-side integrations such as exports.

## Required behavior

- `slug` must be stable and unique.
- `app_config` must point at the Django app config class.
- `urlconf` must point at the domain URL module.
- Plugins mounted under `/sources/` must set `mount_in_hub=True`.
- Plugins contributing explorer counters must provide both `explorer_context_var` and `published_count_getter`.

## Discovery model

- The `sources` hub discovers plugins by scanning installed Django apps and importing `<app>.plugin` when present.
- Plugins are resolved at runtime from installed apps instead of being hard-coded in the core registry.
- Third-party plugins can participate as long as they are installed Django apps and expose the same contract.

## Optional `exports.py` contract

Plugins that declare the `exports` capability may expose an `EXPORTS` iterable in `<app>.exports`.
Each entry must be a `SourceDomainExport` instance with:

- `model_label`
- `filterset`
- `serializer`
- `renderers`

The file export subsystem discovers these export adapters dynamically through the source-domain registry rather than importing concrete domain apps in core code.

## Optional capabilities

Capabilities are descriptive metadata used to document what a plugin provides.
Typical values include `api`, `exports`, `forms`, `html_views`, `signals`, `tasks`, `templates`, `static_assets`, and `legacy_redirects`.

## Current migration state

The registry is now discovery-driven for installed source-domain apps.
Only plugins that opt into `mount_in_hub=True` are mounted automatically under `/sources/`.
Other source-domain apps can keep their current public entry points until their URLs are migrated behind the hub.

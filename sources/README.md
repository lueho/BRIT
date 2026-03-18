# Sources hub and domain plugin contract

The `sources` package is the hub for BRIT source-domain applications.
Each domain package remains a normal Django app, but it should also publish a minimal plugin descriptor so the hub can discover it explicitly.

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

## Required behavior

- `slug` must be stable and unique.
- `app_config` must point at the Django app config class.
- `urlconf` must point at the domain URL module.
- Plugins mounted under `/sources/` must set `mount_in_hub=True`.
- Plugins contributing explorer counters must provide both `explorer_context_var` and `published_count_getter`.

## Optional capabilities

Capabilities are descriptive metadata used to document what a plugin provides.
Typical values include `api`, `exports`, `forms`, `html_views`, `signals`, `tasks`, `templates`, `static_assets`, and `legacy_redirects`.

## Current migration state

The registry is explicit and in-repo.
Only plugins that opt into `mount_in_hub=True` are mounted automatically under `/sources/`.
Other source-domain apps can keep their current public entry points until their URLs are migrated behind the hub.

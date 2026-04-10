# Sources hub and domain plugin contract

The `sources` package is the hub for BRIT source-domain applications.
Each domain package remains a normal Django app, but it should also publish a minimal plugin descriptor so the hub can discover it explicitly.
Core code in `sources` should not import built-in domain apps directly. Integration should happen through installed-app discovery and the shared plugin contract.

## What "source" and "domain" mean here

In this context, a `source` is the real-world origin of a bioresource: where it is generated, through which activity or system it arises, and under which conditions it becomes available.

A `domain` is the thematic class of such origins, with its own concepts, estimation logic, data model, and user workflows.

Examples of source domains include waste-collection systems, roadside trees, greenhouses, and urban green spaces.

## Disambiguation glossary

- `source` in the `sources` app means a bioresource origin or generation context.
- `reference` means a bibliographic or documentary information source, currently modeled by `bibliography.Source`.
- a reference can describe a source domain object, but it is not itself a bioresource source.

For user-facing text, prefer `origin` or `bioresource source` when referring to the `sources` app concept, and prefer `reference` when referring to bibliography objects.

## What a source-domain plugin is

A source-domain plugin is an installed Django app that publishes a small descriptor so the `sources` hub can discover and integrate it without hard-coded core imports.

The plugin exists to let the core hub answer three questions:

- which source domain is this
- where are its Django entrypoints
- which optional integrations does it contribute

The domain app still owns its own implementation details such as models, views, templates, serializers, filters, exports, and tests.
The `sources` core app is responsible for discovery, hub composition, and shared orchestration.

## What a source-domain app provides in BRIT

For users, a source-domain app is not just a technical plugin. It is the place where one class of bioresource origin becomes understandable and usable inside BRIT.

A source-domain app typically provides:

- structured access to one source domain such as waste-collection systems, roadside trees, or greenhouses
- descriptions of where and how a bioresource is generated within that domain
- domain-specific views that let users browse, inspect, compare, map, and sometimes export source-related records
- estimation logic, parameters, or contextual indicators that help users assess generated amounts and availability
- a shared vocabulary and data model that turn heterogeneous real-world generation contexts into consistent BRIT objects

In practice, a source-domain app is how BRIT turns complex real-world bioresource generation contexts into something users can actually explore, compare, and reuse.

## Role in the BRIT bioresource ecosystem

Within BRIT, source-domain apps form the supply-side context layer of the platform: they describe where bioresources come from, how they are generated, and how their quantities can be interpreted or estimated.

They help the platform:

- represent the physical origin of bioresources in structured domain models
- normalize generation contexts into stable concepts and structured records
- expose source-related knowledge to user-facing tools such as maps, filters, exports, and explorer views
- provide upstream context that other parts of BRIT can build on when interpreting materials, processes, inventories, or regional conditions

In that sense, source-domain apps are not isolated feature modules. They are domain-specific entrypoints through which the wider BRIT ecosystem understands the origin, generation, and potential availability of bioresources.

## What a source-domain plugin is intended to do

- identify a source domain through a stable `slug` and human-readable `verbose_name`
- declare the app's Django entrypoints through `app_config` and `urlconf`
- advertise optional capabilities such as hub mounting, explorer participation, or exports
- keep domain-specific implementation inside the plugin app rather than moving it into `sources` core

## Minimum viable plugin

The minimum viable source-domain plugin is:

- an installed Django app in `INSTALLED_APPS`
- with a `plugin.py` module
- exposing a module-level `plugin` value that is a `SourceDomainPlugin` instance
- with valid `slug`, `verbose_name`, `app_config`, and `urlconf` values

A minimum viable plugin does not need to mount under `/sources/`, contribute explorer counters, or provide exports.

## Common plugin-owned files

In practice, most built-in source-domain plugins also own files such as:

- `apps.py`
- `models.py`
- `admin.py`
- `urls.py`
- `plugin.py`
- `tests/`

These are common domain-app files, not the strict minimum contract required for discovery.

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

## Which core resources a plugin can rely on

The plugin model is intentionally small: the core `sources` app consumes explicit plugin declarations rather than exposing a large internal API.

The currently stable integration surfaces are:

- `sources.contracts.SourceDomainPlugin`
- `sources.contracts.SourceDomainExport`
- the `<app>.plugin` discovery convention
- the optional `<app>.exports` convention for plugins with the `exports` capability
- hub mounting through `mount_in_hub` and `mount_path`
- explorer participation through `explorer_context_var` and `published_count_getter`

Everything else inside `sources` should be treated as core implementation detail unless it is documented here.

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

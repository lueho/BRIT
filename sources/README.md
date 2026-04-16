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

## Typical parts of a source-domain app

Although source domains differ in subject matter, they usually combine the same kinds of concerns.

- geographic origin data
  - where the bioresource arises
  - administrative areas, catchments, sites, facilities, routes, or mapped features
- descriptive data and analysis
  - how the bioresource has been generated, collected, maintained, harvested, or otherwise made available
  - this covers raw observations, status-quo records, historical records, and statistical analysis describing past or current conditions
  - examples include collection-system settings, operational attributes, management regimes, process descriptions, observed amounts, and observed compositions
- predictive models
  - calibrated models that estimate or predict generated amount, composition, or availability for a given catchment and time span
  - these models are often derived from descriptive data, but they are not the same thing and should remain conceptually distinct
- assumptions and scenarios
  - user-created artificial inputs that represent expert judgment where real-world data is sparse or unavailable
  - this includes explicit assumptions, boundary assumptions such as minimum and maximum values, and reproducible scenario definitions used to run models under different conditions
  - these objects improve usability and planning support, but they must remain clearly separated from observed real-world data
- spatial aspects
  - geometry, regional aggregation, map views, GeoJSON outputs, or location-linked interpretation
- temporal aspects
  - seasons, frequencies, reporting periods, yearly versions, or time-dependent behavior

Descriptive, predictive, and assumption-based parts are closely related but serve different purposes. Descriptive data explains what has been observed or how a system currently works. Predictive models use assumptions or calibrated relationships to estimate what is likely to be generated under defined spatial and temporal conditions. Assumptions and scenarios capture intentional user-defined inputs for planning, exploration, or inventory setup. All three can have spatial and temporal dimensions, but the structure should keep the distinction visible to developers, maintainers, and users.

## Recommended structure for a source-domain app

Source-domain apps should follow a similar internal shape so they stay easy to understand, maintain, and integrate with the `sources` hub.

### Core integration surface

- `apps.py`
  - Django app configuration
- `plugin.py`
  - the domain's `SourceDomainPlugin` descriptor
- `urls.py`
  - the domain's canonical URL configuration

### Domain runtime surface

- `models.py`
  - core domain records describing origin, descriptive observations, predictive model objects, and scenario or assumption objects where applicable
- `views.py`
  - HTML views for browsing, detail, editing, review, descriptive analysis, predictive results, scenario setup, or map pages
- `forms.py`
  - domain-specific editing and filtering forms, including assumption or scenario input forms where relevant
- `filters.py`
  - reusable filtersets for tables, explorer pages, and exports
- `serializers.py`
  - API and export serializers
- `viewsets.py`
  - API endpoints where applicable
- `router.py`
  - domain router wiring when an API surface exists
- `admin.py`
  - admin registration
- `tests/`
  - domain-local tests covering the app's behavior

### Optional but common domain integration modules

- `selectors.py`
  - small read-model helpers such as published counts and explorer statistics
- `exports.py`
  - `SourceDomainExport` registrations for file export
- `renderers.py`
  - domain-specific export renderers
- `tasks.py`
  - background jobs that belong to the domain
- `signals.py`
  - domain-local signal registration only where needed
- `geojson.py`
  - map-oriented serialization helpers
- `inventory/`
  - domain inventory algorithms or lookup integration
- `templates/`
  - domain templates
- `static/`
  - domain JS/CSS/images
- `management/`
  - domain management commands

### Optional concern-oriented substructure for larger apps

If a domain grows large, organize by concern without breaking the shared outer shape.
Typical internal concern groups are:

- origin and geography
- generation or gathering system description
- descriptive observations and analysis
- predictive estimation or forecasting
- assumptions and scenarios
- temporal interpretation
- map and export presentation

For small apps, keeping these concerns in the main modules is fine.
For larger apps, extract cohesive helpers or subpackages, but keep the main entry modules stable so the app still looks familiar across domains.

Where descriptive, predictive, and assumption-based parts coexist, the app structure and interface should make their difference obvious. Users should be able to tell whether they are looking at observed or recorded domain data, at model-based estimates and predictions derived from that data, or at explicitly user-defined assumptions and scenarios.

## Recommended design principles for source-domain apps

- keep domain logic inside the domain app
  - models, selectors, estimation logic, and views should live with the source domain
- keep hub integration thin and explicit
  - use plugin metadata and shared contracts instead of ad hoc core imports
- separate descriptive data from predictive models
  - descriptive records, descriptive analysis, and calibrated predictive models may be related, but they should not collapse into the same concept in code, docs, or UI
- make the descriptive/predictive distinction legible in the interface
  - users should be able to recognize whether a value is observed, aggregated from observations, statistically described, or model-predicted
- keep assumptions and scenarios separate from observed data
  - user-defined artificial inputs are valuable, but they must be stored and presented as assumptions rather than being mixed into real-world evidence
- design for reproducibility and track record
  - scenario definitions, assumption values, model inputs, and resulting outputs should be storable, reviewable, and repeatable later
- treat spatial and temporal behavior as cross-cutting concerns
  - do not force them into separate apps if they belong naturally to the same source domain
- prefer shared core helpers over one-off integration code
  - if multiple domains need the same integration pattern, the `sources` core should own it

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
- `forms.py`
- `views.py`
- `filters.py`
- `serializers.py`
- `viewsets.py`
- `router.py`
- `selectors.py`
- `exports.py`
- `renderers.py`
- `tasks.py`
- `signals.py`
- `geojson.py`
- `inventory/`
- `templates/`
- `static/`
- `management/`

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
- `published_count_getter`
- `explorer_card`
- `legacy_redirects`
- `map_mount`
- `public_mount`
- `sitemap_items`
- `geojson_cache_warmer`

`app_config` is also used to derive the app module path for optional plugin-side integrations such as exports.

## Which core resources a plugin can rely on

The plugin model is intentionally small: the core `sources` app consumes explicit plugin declarations rather than exposing a large internal API.

The currently stable integration surfaces are:

- `sources.contracts.SourceDomainPlugin`
- `sources.contracts.SourceDomainExplorerCard`
- `sources.contracts.SourceDomainLegacyRedirects`
- `sources.contracts.SourceDomainMapMount`
- `sources.contracts.SourceDomainPublicMount`
- `sources.contracts.SourceDomainExport`
- the `<app>.plugin` discovery convention
- the optional `<app>.exports` convention for plugins with the `exports` capability
- hub mounting through `mount_in_hub` and `mount_path`
- explorer participation through `explorer_card` and `published_count_getter`
- root-level public mounts through `public_mount`
- map URL composition through `map_mount`
- compatibility redirects through `legacy_redirects`
- source-owned sitemap contributions through `sitemap_items`
- GeoJSON cache warmer orchestration through `geojson_cache_warmer`

Everything else inside `sources` should be treated as core implementation detail unless it is documented here.

## Core helpers provided today

At the moment, the `sources` hub provides a small but useful set of integration helpers.

- contracts in `sources.contracts`
  - `SourceDomainPlugin` defines the basic plugin descriptor
  - `SourceDomainExplorerCard` defines explorer card metadata
  - `SourceDomainLegacyRedirects` defines plugin-owned compatibility redirects
  - `SourceDomainMapMount` defines plugin-owned map URL mounts
  - `SourceDomainPublicMount` defines plugin-owned root-level public mounts
  - `SourceDomainExport` defines export registrations
- registry functions in `sources.registry`
  - `get_source_domain_plugins()` returns all discovered plugins
  - `get_source_domain_plugin(slug)` resolves a plugin by slug
  - `get_hub_source_domain_plugins()` returns plugins mounted into the hub URL surface
  - `get_source_domain_explorer_cards()` returns explorer card metadata with published counts
  - `get_source_domain_legacy_redirects()` returns plugin-declared legacy redirect mounts
  - `get_source_domain_map_mounts()` returns plugin-declared map URL mounts
  - `get_source_domain_public_mounts()` returns plugin-declared root-level public mounts
  - `get_source_domain_sitemap_items()` returns deduplicated plugin sitemap entries
  - `get_source_domain_geojson_cache_warmers()` returns plugin-owned GeoJSON warmers
- helper methods on `SourceDomainPlugin`
  - `get_app_module()` resolves the app module path from `app_config`
  - `get_urlpatterns()` resolves URL patterns from `urlconf`
  - `get_published_count()` resolves the configured published-count getter
  - `get_geojson_cache_warmer()` resolves the configured warmer task
- hub URL composition in `sources.urls`
  - plugins that opt into hub mounting are included automatically
- explorer composition in `sources.views.SourcesExplorerView`
  - the explorer view consumes registry-built plugin card metadata instead of hard-coded domain counts
- root URL composition in `brit.urls`
  - plugin-declared public mounts, legacy redirects, and map mounts are included without hard-coded domain imports
- sitemap composition in `brit.sitemap_items`
  - plugin-declared sitemap entries are appended dynamically through the registry
- GeoJSON warming in `maps.tasks` and `maps.management.commands.warm_geojson_cache`
  - core orchestration iterates plugin-declared warmers instead of importing domain tasks directly
- export discovery through `utils.file_export.registry_init`
  - plugins with the `exports` capability can register file exports without core hard-coded imports

These helpers should be preferred over custom cross-app glue when integrating a new source-domain app.

## Shared BRIT functionality source-domain apps should reuse

Source-domain apps should not only reuse the narrow `sources` plugin contract. They should also build on the shared BRIT platform modules that already solve recurring problems such as ownership, review, referencing, and map interaction.

The goal is to keep source-domain code relatively high level: domain apps should focus on domain models, domain logic, and domain-specific workflows, while cross-cutting infrastructure should come from shared modules.

### User-created objects and review workflow

If a source-domain record is created or curated by users, it should normally build on `utils.object_management` rather than implementing its own ownership or moderation flow.

Key reusable surfaces include:

- `utils.object_management.models.UserCreatedObject`
  - shared owner tracking
  - shared publication states: `private`, `review`, `published`, `declined`, `archived`
  - shared transition methods such as `submit_for_review()`, `withdraw_from_review()`, `approve()`, `reject()`, and `archive()`
- `utils.object_management.models.ReviewAction`
  - shared audit trail for submission, approval, rejection, withdrawal, and comments
- `utils.object_management.permissions`
  - centralized permission checks and queryset filtering
  - helpers such as `filter_queryset_for_user()`, `apply_scope_filter()`, and `get_object_policy()`
- `utils.object_management.views`
  - generic CRUD, modal CRUD, review, list, autocomplete, and filter views for `UserCreatedObject` models
- `utils.object_management.viewsets.UserCreatedObjectViewSet`
  - shared API behavior for publication scopes and review actions
- `utils.forms.UserCreatedObjectFormMixin`
  - shared backend permission validation for form fields that reference user-created objects

Source-domain apps should therefore prefer:

- inheriting from `UserCreatedObject` for reviewable domain content
- using the existing review workflow instead of inventing custom review states or moderator actions
- using shared permission and policy helpers so templates and APIs stay consistent with backend behavior
- using the shared generic views and viewsets as a base where possible, only adding domain-specific behavior on top

### Maps and spatial user interface

Source-domain apps with spatial data should reuse the existing `maps` module for geometry editing, map configuration, and GeoJSON delivery instead of shipping custom one-off map infrastructure.

Key reusable surfaces include:

- `maps.forms`
  - geometry editing forms based on `LeafletWidget`
  - reusable region, catchment, and geodataset forms that show the expected integration style
- `maps.views.MapMixin`
  - shared map-context construction for pages that need an attached `MapConfiguration`
- `maps.models`
  - `MapConfiguration`, `MapLayerConfiguration`, and `ModelMapConfiguration` for configurable map display
  - reusable geographic objects such as regions, catchments, polygons, and geodatasets
- `maps.serializers.MapConfigurationSerializer`
  - shared frontend map configuration serialization
- `maps.mixins.CachedGeoJSONMixin`
  - shared GeoJSON endpoint behavior with caching, bbox filtering, versioning, and streaming support for larger datasets

Source-domain apps should therefore prefer:

- storing and exposing geometry through the shared maps stack where possible
- using shared map configuration and layer concepts for display
- using the established GeoJSON and map-view patterns instead of creating separate frontend map conventions
- integrating domain-specific map layers into the existing map system rather than building custom spatial UI from scratch

### Bibliographic references

Source-domain apps should use the `bibliography` module for documentary references instead of inventing domain-local citation models.

Key reusable surfaces include:

- `bibliography.models.Source`
  - the shared model for bibliographic references
- `bibliography` author, licence, URL validation, and reference-management functionality
  - shared handling of reference metadata rather than domain-local implementations
- `utils.forms.SourcesFieldMixin`
  - shared form integration for a `sources` many-to-many field that points to `bibliography.Source`
  - includes the reference selection widget and autocomplete integration

Source-domain apps should therefore prefer:

- linking domain records to `bibliography.Source` for references
- using the shared reference widget and autocomplete flow in forms
- relying on the bibliography app for reference creation and maintenance rather than duplicating reference fields inside the domain app

### Shared form, filter, and selection patterns

Source-domain apps should also reuse BRIT's general UI plumbing where it already exists.

Important examples include:

- `utils.forms.SourcesFieldMixin`
  - for reference selection
- `utils.forms.UserCreatedObjectFormMixin`
  - for secure object-reference validation in forms
- `utils.object_management.views` autocomplete and select-option views
  - for ownership-aware object picking
- `utils.filters.BaseCrispyFilterSet`
  - for consistent filter-form rendering

The intent is not that every domain app must look identical. The intent is that source-domain apps should share the same platform-level behavior for review, permissions, map interaction, and referencing, so domain code stays focused on the source domain itself.

## Current optional integration responsibilities

Optional plugin metadata should be used only when the plugin actually participates in that integration surface.

- `mount_in_hub` and `mount_path`
  - mount the plugin under the `/sources/` hub URL surface
- `explorer_card` and `published_count_getter`
  - contribute an explorer card with a live published-object count
- `public_mount`
  - expose a root-level public URL mount owned by the plugin
- `map_mount`
  - expose a plugin-owned map URL mount
- `legacy_redirects`
  - expose compatibility redirects owned by the plugin
- `sitemap_items`
  - contribute canonical URL paths to the composed sitemap list
- `geojson_cache_warmer`
  - let maps orchestration warm plugin-owned GeoJSON caches without direct imports
- `exports` capability plus `<app>.exports`
  - register plugin-owned file exports through the shared export discovery path

## Required behavior

- `slug` must be stable and unique.
- `app_config` must point at the Django app config class.
- `urlconf` must point at the domain URL module.
- Plugins mounted under `/sources/` must set `mount_in_hub=True`.
- `mount_path` requires `mount_in_hub=True`.
- Plugins contributing explorer cards must provide both `explorer_card` and `published_count_getter`.
- `public_mount`, when present, must be a `SourceDomainPublicMount` with a unique `mount_path`.
- `map_mount`, when present, must be a `SourceDomainMapMount`.
- `legacy_redirects`, when present, must be a `SourceDomainLegacyRedirects`.
- `sitemap_items` must be a tuple of strings.
- `geojson_cache_warmer`, when present, must be a dotted task path string.
- Plugins declaring the `exports` capability must provide `<app>.exports`.

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

## Optional capabilities

Capabilities are descriptive metadata used to document what a plugin provides.
Typical values include `api`, `exports`, `forms`, `html_views`, `signals`, `tasks`, `templates`, `static_assets`, and `legacy_redirects`.

## Current architecture state

- The registry is discovery-driven for installed source-domain apps.
- Hub routing, explorer cards, public mounts, map mounts, compatibility redirects, sitemap entries, and GeoJSON warmers are all composed from plugin metadata.
- Plugins can still own canonical public URLs outside `/sources/` through explicit mount metadata rather than core hard-coded imports.

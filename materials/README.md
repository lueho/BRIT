# Materials Module

## Overview

The `materials` app manages the current BRIT implementation for bioresource definitions, laboratory-style sample data, compositions, and measurement-related metadata.

## Documentation Intent

- **This README describes the current implementation**
  It is intended as a current-state module overview for contributors.

- **The roadmap is consolidated in one document**
  Use [Materials database target-state plan](../docs/04_design_decisions/2026-04-14_materials_database_target_state_plan.md) as the single authoritative roadmap for the materials module. The property-unification and unit-handling ADRs remain supporting architecture context rather than separate materials roadmap documents.

## Scope

- **Catalogue layer**
  Materials, material components, and material categories.

- **Sampling layer**
  Sample series and individual samples, including temporal context.

- **Composition layer**
  Component groups, persisted compositions, and weight shares.

- **Measurement layer**
  Materials-specific properties, property values, raw component measurements, and analytical methods.

## Main Concepts

### Materials and components

- **`MaterialCategory`**
  Categorizes materials.

- **`BaseMaterial`**
  Shared base model for material-like objects.

- **`Material`**
  Proxy model for materials.

- **`MaterialComponent`**
  Proxy model for components used in compositions and measurements.

### Samples and time context

- **`SampleSeries`**
  Groups comparable samples over time.

- **`Sample`**
  Stores a concrete sampling event and links to sources, properties, and measurements.

### Compositions

- **`MaterialComponentGroup`**
  Groups components into a composition domain.

- **`Composition`**
  Stores composition settings for a sample and group.

- **`WeightShare`**
  Stores composition values for components within a composition.

### Measurements and methods

- **`MaterialProperty`**
  Defines a materials-specific property.

- **`MaterialPropertyGroup`**
  Groups related properties for aggregation logic.

- **`MaterialPropertyValue`**
  Stores a measured property value with value-level unit metadata and optional basis and analytical-method metadata.

- **`ComponentMeasurement`**
  Stores raw per-sample component measurements with unit, basis, and provenance context.

- **`AnalyticalMethod`**
  Stores laboratory method metadata and related sources.

## Current Composition Handling

- **Persisted composition path**
  `Composition` and `WeightShare` remain active persisted structures in the current app.

- **Raw measurement path**
  `ComponentMeasurement` stores raw per-sample component measurements with unit, basis, and provenance context.

- **Derived read behavior already exists**
  Some current read paths derive composition displays from raw component measurements when persisted composition rows are absent.

- **Roadmap is separate**
  Any future shift in canonical storage or normalization strategy is tracked in the materials target-state plan rather than in this README.

## App Boundaries

- **Depends on `bibliography`**
  For sources and references.

- **Depends on `distributions`**
  For temporal distributions and timesteps.

- **Used by other domains**
  Inventory, case-study, and reporting workflows can build on materials data.

## Data Entry Notes

- **Interactive workflows**
  Material data is primarily managed through BRIT views and admin-supported workflows.

- **Excel import**
  The old CLI Excel import path is deprecated. Use the supported admin or view-based import workflow instead of relying on an old command-line path.

## Documentation Boundaries

- **Development commands**
  See [Developer Guidelines](../docs/02_developer_guide/guidelines.md).

- **Deployment and runtime operations**
  See [Operations](../docs/03_operations/operations.md).

- **Architecture context**
  See [Architecture Overview](../docs/02_developer_guide/architecture.md).

_Last updated: 2026-04-14_
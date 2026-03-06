# Materials Module

## Overview

The `materials` app manages bioresource definitions, laboratory-style sample data, compositions, and measurement-related metadata.

## Scope

- **Catalogue layer**
  Materials, material components, and material categories.

- **Sampling layer**
  Sample series and individual samples, including temporal context.

- **Composition layer**
  Component groups, compositions, and weight shares.

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
  Stores a measured property value and related metadata.

- **`ComponentMeasurement`**
  Stores raw component measurements for a sample.

- **`AnalyticalMethod`**
  Stores laboratory method metadata and related sources.

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

_Last updated: 2026-03-06_
# Materials Module

## Overview
The Materials module is a core component of the Bioresource Inventory Tool (BRIT) that provides comprehensive functionality for managing and analyzing material data. It enables users to define materials, their components, properties, and samples, supporting detailed characterization of bioresources.

## Features
- Material categorization and classification
- Component-based material composition management
- Sample and sample series management
- Temporal distribution of material properties
- Analytical method documentation
- Property value tracking
- Weight share calculations
- Integration with bibliographic sources

## Models

### Material Classification
- **MaterialCategory**: Simple categorization for materials
- **BaseMaterial**: Base class for all material types
- **Material**: Generic material class for many purposes

### Components and Compositions
- **MaterialComponent**: Components of materials (e.g., total solids, volatile solids)
- **MaterialComponentGroup**: Groups of components that form a composition
- **Composition**: Settings for component groups for each material
- **WeightShare**: Actual values of weight fractions in material compositions

### Samples and Properties
- **SampleSeries**: Series of samples taken from a comparable source at different times
- **Sample**: Representation of a single sample taken at a specific location and time
- **MaterialProperty**: Properties of materials with units
- **MaterialPropertyValue**: Values for material properties

### Analysis
- **AnalyticalMethod**: Represents laboratory procedures for analysis

## Entity Relationship Diagram

```mermaid
erDiagram
    NamedUserCreatedObject ||--|{ BaseMaterial : "inherits"
    NamedUserCreatedObject ||--|{ MaterialComponentGroup : "inherits"
    NamedUserCreatedObject ||--|{ MaterialProperty : "inherits"
    NamedUserCreatedObject ||--|{ SampleSeries : "inherits"
    NamedUserCreatedObject ||--|{ AnalyticalMethod : "inherits"

    BaseMaterial ||--o{ SampleSeries : "has"
    BaseMaterial ||--o{ Sample : "categorizes"
    BaseMaterial }o--o{ MaterialCategory : "belongs_to"
    BaseMaterial ||--|{ Material : "proxy"
    BaseMaterial ||--|{ MaterialComponent : "proxy"
    
    SampleSeries ||--o{ Sample : "contains"
    SampleSeries }o--o{ TemporalDistribution : "uses"
    SampleSeries }o--|| Timestep : "has_default"
    
    Sample ||--o{ Composition : "has"
    Sample }o--o{ MaterialPropertyValue : "has_properties"
    Sample }o--o{ Source : "references"
    Sample }o--|| Timestep : "belongs_to"
    Sample }o--|| SampleSeries : "belongs_to"
    
    Composition ||--o{ WeightShare : "contains"
    Composition }o--|| MaterialComponentGroup : "belongs_to"
    Composition }o--|| MaterialComponent : "fractions_of"
    Composition }o--o{ TemporalDistribution : "has"
    
    WeightShare }o--|| MaterialComponent : "of"
    
    MaterialProperty ||--o{ MaterialPropertyValue : "defines"
    
    AnalyticalMethod }o--o{ Source : "references"
    
    MaterialCategory {
        string name
    }
    
    BaseMaterial {
        string name
        string type
        Owner owner
    }
    
    Material {
        string name
        string type
    }
    
    MaterialComponent {
        string name
        string type
    }
    
    MaterialComponentGroup {
        string name
        Owner owner
    }
    
    SampleSeries {
        string name
        boolean publish
        Material material
        TemporalDistribution temporal_distribution
        Timestep default_timestep
    }
    
    Sample {
        string name
        Material material
        datetime datetime
        string location
        SampleSeries series
        Timestep timestep
        ImageField image
    }
    
    Composition {
        Sample sample
        MaterialComponentGroup group
        MaterialComponent fractions_of
        int order
    }
    
    WeightShare {
        MaterialComponent component
        Composition composition
        decimal average
        decimal standard_deviation
    }
    
    MaterialProperty {
        string name
        string unit
    }
    
    MaterialPropertyValue {
        MaterialProperty property
        float average
        float standard_deviation
    }
    
    AnalyticalMethod {
        string name
        string technique
        string standard
        string instrument_type
        string lower_detection_limit
        URL ontology_uri
    }
```

## Views
The module provides a comprehensive set of views for managing material data:
- CRUD operations for materials, components, and samples
- Sample series management
- Composition and weight share management
- Property value tracking
- Analytical method documentation
- Integration with bibliographic sources

## Integration
The Materials module integrates with other BRIT modules:
- Bibliography module for data sources
- Distributions module for temporal aspects of material properties
- Case Studies modules for specialized material analysis
- Inventories module for material availability calculations

## Usage
This module is used throughout BRIT to:
- Define and categorize bioresource materials
- Characterize material compositions and properties
- Track samples and their analysis results
- Support temporal analysis of material characteristics
- Provide the foundation for bioresource inventory calculations
# CLOSECYCLE Case Study Module

## Overview
The CLOSECYCLE module is a case study implementation within the Bioresource Inventory Tool (BRIT) for the CLOSECYCLE project's Territorial Biorefinery Networks (TBN). It provides tools for managing showcases — the pilots of the TBNs — and for mapping biogas plants, particularly in Sweden.

## Features
- Management of showcases for Territorial Biorefinery Networks
- Showcase connections to materials (by role), samples, sample series and ordered process chains
- Linkage of inventory scenarios to showcases
- Spatial representation of biogas plants in Sweden
- Map visualization of showcases and pilot regions
- Integration with regional data

## Models

### Showcase
A CLOSECYCLE showcase demonstrates best practices or innovative solutions for the valorization of residue-based bioresources to make products for use within the showcase region. Each showcase is a TBN pilot and combines:

- Basic information (name, description)
- Associated `region` (NUTS anchor) and optional `catchment` (TBN region)
- `materials` via `ShowcaseMaterial` — bioresources (input), intermediates and products
- `processes` via `ShowcaseProcess` — the ordered processing chain
- `samples` and `sample_series` — measured material data
- `scenarios` — inventory scenarios defined in the inventories module

Together these connections describe a showcase as an inventory plus a material-flow structure through a processing chain.

### ShowcaseMaterial
Links a showcase to a material with a role (`input`, `intermediate`, `product`) and an optional display order.

### ShowcaseProcess
Links a showcase to a process at a position in the processing chain (`order`).

### BiogasPlantsSweden
Represents biogas plants in Sweden with detailed attributes:
- Geographic location (point geometry)
- Plant identification (type, name)
- Location details (county, city, municipality)
- Technical information (creation year, size, technology type)
- Classification (main type, sub-type)
- Upgrade potential

## Views
The module provides views for managing showcase data:
- List views for published and private showcases
- Map view for visualizing showcases and pilot regions
- CRUD operations with inline formsets for material and process links
- Autocomplete endpoint for scenario–showcase assignment

## Integration
The CLOSECYCLE module integrates with other BRIT modules:
- Maps module for spatial representation and catchments (TBN regions)
- Materials module for materials, samples and sample series
- Processes module for the processing chain
- Inventories module for showcase-linked scenarios

## Usage
This module provides tools for:
- Documenting CLOSECYCLE showcases and their processing chains
- Analyzing the distribution of biogas plants
- Mapping TBN regions for biorefinery implementation
- Supporting decision-making for closing material cycles in bioresource management

The CLOSECYCLE module aims to promote the concept of closing material cycles in bioresource management through practical showcases and real-world examples of biogas plants and territorial biorefinery networks.

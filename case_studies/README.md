# Case Studies Module

## Overview
The Case Studies module contains the remaining case-study application within the Bioresource Inventory Tool (BRIT).

## Case Studies

### CloseCycle
A case study focused on closing material cycles in bioresource management.

## Structure
The remaining case study is implemented as a separate Django application within the module:
- `closecycle/` - Implementation of the CloseCycle case study

Former case-study apps have been migrated into `sources/`:
- `sources/roadside_trees/` - FLEXIBI Hamburg
- `sources/greenhouses/` - FLEXIBI Nantes
- `sources/waste_collection/` - SOILCOM waste collection

## Integration
The remaining case-study app integrates with other BRIT modules, particularly:
- Maps module for spatial visualization
- Inventories module for data collection
- Materials module for material characterization
- Bibliography module for references

CloseCycle implements custom models, views, and templates specific to its research focus while leveraging the core functionality provided by the main BRIT modules.
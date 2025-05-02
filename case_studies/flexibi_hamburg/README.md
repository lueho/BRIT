# FLEXIBI Hamburg Case Study Module

## Overview
The FLEXIBI Hamburg module is a case study implementation within the Bioresource Inventory Tool (BRIT) focused on urban bioresources in Hamburg, Germany. It was developed as part of the FLEXIBI project, an ERA-NET project funded by the German Ministry of Education and Research (BMBF), which studied the potential of residues from urban and peri-urban areas as feedstocks for Small-Scale Flexi-Feed Biorefineries (SFB).

## Features
- Spatial representation of urban vegetation in Hamburg
- Detailed data on roadside trees including species, location, and dimensions
- Information on green areas including size, type, and ownership
- Map visualization of urban vegetation
- Data export functionality
- Integration with catchment areas

## Models

### HamburgRoadsideTrees
Represents trees along roadsides in Hamburg with detailed attributes:
- Geographic location (point geometry)
- Tree identification (ID, genus, species in Latin and German)
- Physical characteristics (crown diameter, trunk circumference)
- Planting information (year)
- Location details (street, house number, district)

### HamburgGreenAreas
Represents green spaces in Hamburg:
- Geographic boundaries (multipolygon geometry)
- Identification (name, ID)
- Location details (district)
- Size information (area in square meters and hectares)
- Type of green space
- Ownership information

## Views
The module provides views for visualizing and accessing the data:
- Map views for displaying roadside trees
- Iframe-compatible map views for embedding
- File export functionality for roadside tree data
- Autocomplete functionality for selecting catchments

## Integration
The FLEXIBI Hamburg module integrates with other BRIT modules:
- Maps module for spatial representation and visualization
- Catchment functionality for defining areas of interest
- File export utilities for data extraction

## Usage
This module provides valuable data on urban vegetation in Hamburg, which can be used to:
- Assess the potential of urban bioresources
- Plan for sustainable urban forestry
- Analyze the distribution of green spaces in the city
- Support decision-making for urban planning and resource management

The data and functionality support the FLEXIBI project's goal of studying residues from gardening, landscaping, and urban areas as potential feedstocks for biorefineries.
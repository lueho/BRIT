# CLOSECYCLE Case Study Module

## Overview
The CLOSECYCLE module is a case study implementation within the Bioresource Inventory Tool (BRIT) focused on demonstrating possibilities for Territorial Biorefinery Hubs. It provides tools for showcasing biorefinery concepts and mapping biogas plants, particularly in Sweden.

## Features
- Management of showcase projects for Territorial Biorefinery Hubs
- Spatial representation of biogas plants in Sweden
- Map visualization of showcases and pilot regions
- Integration with regional data

## Models

### Showcase
Represents demonstration projects for Territorial Biorefinery Hubs:
- Basic information (name, description)
- Associated region
- Used to highlight possibilities and best practices in biorefinery implementation

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
- CRUD operations for showcase management

## Integration
The CLOSECYCLE module integrates with other BRIT modules:
- Maps module for spatial representation and visualization
- Region functionality for defining areas of interest

## Usage
This module provides tools for:
- Demonstrating biorefinery hub concepts
- Analyzing the distribution of biogas plants
- Showcasing pilot regions for biorefinery implementation
- Supporting decision-making for closing material cycles in bioresource management

The CLOSECYCLE module aims to promote the concept of closing material cycles in bioresource management through practical showcases and real-world examples of biogas plants and biorefinery hubs.
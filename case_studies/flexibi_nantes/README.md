# FLEXIBI Nantes Case Study Module

## Overview
The FLEXIBI Nantes module is a case study implementation within the Bioresource Inventory Tool (BRIT) focused on greenhouse cultivation and plant growth cycles in Nantes, France. It was developed as part of the FLEXIBI project, an ERA-NET project funded by the German Ministry of Education and Research (BMBF), which studied the potential of residues from agricultural and horticultural activities as feedstocks for Small-Scale Flexi-Feed Biorefineries (SFB).

## Features
- Detailed modeling of greenhouse cultivation systems in Nantes
- Tracking of plant growth cycles and their temporal aspects
- Management of different cultures (plant types) grown in greenhouses
- Spatial representation of greenhouse locations
- Calculation of biomass shares at different growth stages
- Data visualization through maps
- Data export functionality

## Models

### Greenhouse
Represents greenhouse cultivation facilities in Nantes:
- Basic information (name, description)
- Spatial location
- Associated growth cycles
- Methods for accessing components, shares, and configurations
- Functionality for grouping and sorting growth cycles

### Culture
Represents types of plants grown in greenhouses:
- Name and description
- Associated with greenhouse growth cycles

### GreenhouseGrowthCycle
Represents growth cycles of plants in greenhouses:
- Start and end dates
- Associated greenhouse and culture
- Methods for tracking values at different timesteps
- Functionality for generating table data for visualization

### GrowthTimeStepSet
Represents sets of timesteps for growth cycles:
- Associated growth cycle
- Methods for adding components

### GrowthShare
Represents shares of components at different timesteps:
- Value (percentage or amount)
- Associated component and timestep

## Views
The module provides a complete set of views for managing greenhouse data:
- CRUD operations for Cultures
- CRUD operations for Greenhouses
- Management of Greenhouse Growth Cycles
- Updating of Growth Timestep Sets
- Map visualization of greenhouse locations
- File export functionality

## Integration
The FLEXIBI Nantes module integrates with other BRIT modules:
- Maps module for spatial representation
- Materials module for component tracking
- Distributions module for temporal aspects

## Usage
This module provides valuable data on greenhouse cultivation in Nantes, which can be used to:
- Assess the potential of horticultural residues as bioresources
- Analyze growth cycles and biomass production
- Plan for sustainable management of greenhouse residues
- Support decision-making for biorefinery feedstock sourcing

The data and functionality support the FLEXIBI project's goal of studying residues from horticultural activities as potential feedstocks for biorefineries.
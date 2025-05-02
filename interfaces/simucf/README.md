# SimuCF Interface Module

## Overview
The SimuCF Interface module provides integration between the Bioresource Inventory Tool (BRIT) and SimuCF (Simulation of Carbon Flows), a tool for simulating carbon flows in biological systems. This module enables users to prepare and export material data from BRIT in a format compatible with SimuCF simulations.

## Features
- Filtering of material samples that are compatible with SimuCF
- Validation of biochemical composition data for SimuCF compatibility
- Generation of SimuCF input files based on user-specified parameters
- Serialization of BRIT material data to SimuCF format

## Models

### InputMaterial
A proxy class for the Sample model that:
- Checks compatibility and completeness of stored material samples for SimuCF
- Implements properties required for serialization to SimuCF format
- Provides access to biochemical composition data including:
  - Carbohydrates
  - Amino Acids
  - Starches
  - Hemicellulose
  - Fats
  - Waxes
  - Proteins
  - Cellulose
  - Lignin

### InputMaterialManager
A custom manager for the InputMaterial model that:
- Filters material samples to include only those with complete biochemical composition data
- Ensures that only materials compatible with SimuCF are available for selection

## Views

### SimuCFFormView
A form view that:
- Presents a form for users to select input materials and specify simulation parameters
- Validates user input
- Generates a SimuCF input file based on the selected material and parameters
- Provides the generated file as a downloadable attachment

## Integration
The SimuCF Interface module integrates with:
- Materials module for accessing material samples and their biochemical composition
- SimuCF external tool for carbon flow simulations

## Usage
This module is used when researchers or practitioners want to:
1. Identify materials in BRIT that are suitable for SimuCF simulations
2. Generate input files for SimuCF based on BRIT material data
3. Perform carbon flow simulations using BRIT data

The interface simplifies the process of preparing data for SimuCF, ensuring that only compatible materials are used and that the generated input files follow the required format.
# Case Studies Module

## Overview
The Case Studies module contains implementations of various research projects and case studies within the Bioresource Inventory Tool (BRIT). These case studies demonstrate practical applications of the tool for different bioresource management scenarios.

## Case Studies

### SOILCOM
SOILCOM is a project of the Interreg North Sea Region Programme, co-funded by the European Union. The project focused on sustainable soil management through the utilization of waste streams as a resource for custom-made composts. 

Within work package 4 *Waste Streams* of SOILCOM, BRIT was significantly improved, especially the user interface and usability across all modules. The tool was extended with the *Household Waste Collection* module, which was applied for collaborative data collection on biowaste collection systems in the North Sea Region.

### FLEXIBI Hamburg
The Hamburg component of the FLEXIBI project, which studied the potential of residues from various sources in the Hamburg region as feedstocks for Small-Scale Flexi-Feed Biorefineries (SFB).

### FLEXIBI Nantes
The Nantes component of the FLEXIBI project, focusing on the potential of bioresources in the Nantes region of France.

### CloseCycle
A case study focused on closing material cycles in bioresource management.

## Structure
Each case study is implemented as a separate Django application within the module:
- `closecycle/` - Implementation of the CloseCycle case study
- `flexibi_hamburg/` - Implementation of the FLEXIBI Hamburg case study
- `flexibi_nantes/` - Implementation of the FLEXIBI Nantes case study
- `soilcom/` - Implementation of the SOILCOM case study

## Integration
The case studies integrate with other BRIT modules, particularly:
- Maps module for spatial visualization
- Inventories module for data collection
- Materials module for material characterization
- Bibliography module for references

Each case study may implement custom models, views, and templates specific to its research focus while leveraging the core functionality provided by the main BRIT modules.
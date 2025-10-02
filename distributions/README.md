# Distributions Module

## Overview
The Distributions module is a supporting component of the Bioresource Inventory Tool (BRIT) that provides functionality for managing temporal distributions and timesteps. It enables other modules to organize data with temporal aspects, such as seasonal variations or time-based distributions.

## Features
- Organization of timesteps into named distributions
- Management of periods within distributions
- Support for seasonal data representation
- Integration with other modules for temporal data organization

## Models

### TemporalDistribution
Organizes timesteps into named distributions:
- Name and description
- Examples include "months of the year", "quarters", "seasons", etc.
- Provides a framework for organizing time-based data

### Timestep
Defines a specific point or interval in a temporal distribution:
- Name and order within the distribution
- Associated with a specific temporal distribution
- Examples include individual months, quarters, or seasons
- Provides abbreviated names for compact representation

### Period
Represents a part of a full temporal distribution:
- Start and end timesteps
- Associated with a specific temporal distribution
- Allows for defining custom periods within a distribution (e.g., "summer months", "growing season")

## Views
The module provides minimal views as it primarily serves as a supporting module:
- TimestepModalDetailView - for displaying timestep details in a modal

## Integration
The Distributions module integrates with other BRIT modules that require temporal organization:
- Case Studies modules for tracking seasonal aspects of bioresources
- Materials module for representing seasonal variations in material properties
- Inventories module for organizing inventory data by time periods

## Usage
This module is used throughout BRIT to:
- Organize data with temporal aspects
- Enable seasonal analysis of bioresources
- Support time-based visualizations and calculations
- Provide a consistent framework for representing time periods across the application
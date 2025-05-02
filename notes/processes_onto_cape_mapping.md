# OntoCAPE Mapping for Processes App

This document aligns BRIT’s **Processes** app data structures with the OntoCAPE ontology to maximize semantic compatibility.

---

## OntoCAPE Modules Overview
- **Unit Operation Ontology**: Classes for high-level categories and specific unit operations (e.g., Reactor, Distillation Column).
- **Process Behavior & Modeling**: Templates for dynamic or conceptual process models and sequences of operations.
- **Material Ontology**: Definitions of substances, streams, and material properties.
- **Physical & Chemical Properties**: Quantities like temperature, flow rate, yield, etc.

---

## Class & Field Mapping

| BRIT Class / Field          | OntoCAPE Class                | OntoCAPE Module               | Notes                                                               |
|-----------------------------|-------------------------------|-------------------------------|---------------------------------------------------------------------|
| **ProcessCategory**         | High-level unit operation group (e.g., OperationCategory) | Unit Operation               | Categories in BRIT map to OntoCAPE’s grouping of unit operations.  |
| **ProcessType**             | UnitOperation                 | Unit Operation               | Specific operation type (fermentation, pyrolysis, etc.).           |
| **Process**                 | ProcessModel / CompositeProcess | Process Behavior & Modeling    | Sequence of unit operations; maps to a ProcessModel class.          |
| **ProcessStep**             | Instantiated UnitOperation    | Unit Operation & Process Model | Each step is an occurrence of a UnitOperation within a ProcessModel. |
| **RequiredMaterial**        | Material                      | Material                     | Material stream as feed; OntoCAPE’s Material class.                |
| **PollutantEmission**       | Material                      | Material                     | Output substances flagged as pollutants via MaterialCategory/tag.  |

---

### Parameter & Property Mapping

| BRIT Field                 | OntoCAPE Property Class       | OntoCAPE Module               | Notes                                                              |
|----------------------------|-------------------------------|-------------------------------|--------------------------------------------------------------------|
| mechanism                  | OperationPrinciple            | Physical & Chemical Properties | Captures principle/technology of operation.                        |
| temperature_min / max      | TemperatureRangeProperty      | Physical & Chemical Properties | OntoCAPE’s TemperatureProperty with range constraints.             |
| capacity_min / max         | FlowRateRangeProperty         | Physical & Chemical Properties | Maps to FlowRateProperty or MaterialFlowRate classes.             |
| residence_time_min / max   | TimeDurationProperty          | Process Behavior & Modeling    | Duration of unit operation; maps to TimeDurationProperty.         |
| yield_percentage           | YieldProperty                 | Physical & Chemical Properties | Percentage-based yield metric.                                     |
| capital_cost_min / max     | InvestmentCostProperty        | Economic Properties (not core) | Model as annotation or linked cost metric class in OntoCAPE econ.  |
| operating_cost_min / max   | OperatingCostProperty         | Economic Properties            | Similar to capital cost.                                          |

---

## JSON vs Structured Data
- **Free-form parameters** (e.g., `default_parameters`, `parameters`, `config`) align with OntoCAPE’s **ParameterSet** concept: treated as opaque templates.
- **Metrics JSON** (`energy_consumption`, `environmental_impact`) align with OntoCAPE property classes; if querying is needed, consider migrating to explicit property models.

---

*For deeper alignment, review OntoCAPE’s sub-ontology documentation and adjust field names, constraints, and class URIs accordingly.*

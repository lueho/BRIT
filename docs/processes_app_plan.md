# Processes App – Working Plan

Date: 2025-04-28  
Author: [Your Name]

## 1. Purpose & Scope
- **Goal**: Provide a unified “Processes” app to define, configure and run material-conversion processes.  
- **Context**: Should integrate seamlessly with existing **Materials** module (models, APIs, admin, tests).

### 1.1 User Stories
- **As owner of a residue material**: list available treatment processes for a given material via `/api/processes/?input_material=<material_id>` using `ProcessCompatibility` filters.
- **As a biorefinery planner (demand-driven)**: discover processes that produce a target product via `/api/processes/?output_material=<material_id>`.
- **As a biorefinery planner (adaptation)**: given a set of existing processes (codes), retrieve alternative output products via `/api/processes/alternatives/?process_codes=<code_list>` or service-layer method `list_alternative_outputs(code_list)`.
- **As an NGO**: demonstrate value-added routes by selecting a regional residue material and listing distinct outputs beyond incineration using the above endpoints and presenting richer products.
- **As a manager of a territorial biorefinery network**: identify compatible material combinations (e.g., digestate + wood chips) via `/api/process-types/combinations/?input_materials=<id1,id2>` or service method `list_material_combinations(material_ids)`.

## 2. High-Level Structure

```
brit/
├── processes/             # new Django app
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py
│   ├── services/          # business logic
│   │   └── conversion.py
│   ├── serializers.py     # DRF
│   ├── views.py           # DRF viewsets
│   ├── urls.py
│   ├── admin.py
│   ├── migrations/
│   └── tests/
│       ├── test_models.py
│       ├── test_services.py
│       └── test_api.py
└── docs/
    └── processes_app_plan.md
```

## 3. Data Model

1. **ProcessCategory**  
   - name: CharField(max_length=127)  
   - description: TextField(blank=True)

2. **ProcessType**  
   - code: CharField(max_length=64, unique=True)  
   - name: CharField(max_length=127)  
   - description: TextField(blank=True)  
   - default_parameters: JSONField(default=dict)  
   - category: ForeignKey → ProcessCategory

3. **ProcessInputCompatibility** (through model)  
   - process_type: ForeignKey → ProcessType  
   - material_category: ForeignKey → materials.models.MaterialCategory  
   - compatible: BooleanField(default=True)

4. **ProcessOutputCompatibility** (through model)  
   - process_type: ForeignKey → ProcessType  
   - material_category: ForeignKey → materials.models.MaterialCategory  
   - compatible: BooleanField(default=True)

5. **Process** (runtime instance)  
   - process_type: ForeignKey → ProcessType  
   - input_material: ForeignKey → materials.models.Material  
   - output_material: ForeignKey → materials.models.Material  
   - parameters: JSONField(blank=True)  
   - status: CharField(choices=[PENDING,RUNNING,SUCCESS,FAILURE])  
   - created_at, started_at, finished_at: DateTimeFields

6. **ProcessStep** (optional, multi-step)  
   - process: ForeignKey → Process  
   - step_number: IntegerField  
   - action: CharField(max_length=255)  
   - config: JSONField(blank=True)

### 3.1 Insights from 'Magic Match Filtering' sheet
- **Questions answered:**
  - What high-level process categories exist? (e.g., Biochemical, Thermochemical, Material, Chemical, Syngas)
  - Which specific processes belong to each category? (e.g., Anaerobic digestion, Fast pyrolysis, Gasification technologies, Torrefaction, etc.)
  - Which processes are compatible or should be filtered based on selected criteria.
- **Implied structure:**
  - A `ProcessCategory` model grouping processes by category.
  - Detailed process definitions linked to categories (specific processes list).
  - Many-to-many relationship between `ProcessType` and `MaterialCategory` (or material type) with a `compatible` boolean flag.
  - Service-layer filtering logic selecting processes based on compatibility.

### 3.2 ProcessType Metadata Fields
- **mechanism**: CharField(max_length=255, help_text="Underlying mechanism (e.g. fermentation, pyrolysis)")
- **temperature_min**, **temperature_max**: DecimalField(max_digits=6, decimal_places=2, help_text="Operating temperature range (°C)")
- **capacity_min**, **capacity_max**: DecimalField(max_digits=10, decimal_places=2, help_text="Capacity range (e.g. kg/h)")
- **pressure_min**, **pressure_max**: DecimalField(max_digits=6, decimal_places=2, blank=True, null=True, help_text="Operating pressure range (bar)")
- **residence_time_min**, **residence_time_max**: DurationField(blank=True, null=True, help_text="Residence time range (e.g. hours)")
- **yield_percentage**: DecimalField(max_digits=5, decimal_places=2, help_text="Expected yield (% of input)")
- **energy_consumption**: JSONField(blank=True, default=dict, help_text="Energy metrics, e.g. {'electricity_kwh_per_ton':..., 'heat_mj_per_ton':...}")
- **catalyst**: CharField(max_length=255, blank=True, help_text="Catalyst or reagent used, if any")
- **capital_cost_min**, **capital_cost_max**: DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, help_text="Capital cost per unit capacity (USD)")
- **operating_cost_min**, **operating_cost_max**: DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, help_text="Operational cost per unit output (USD)")
- **environmental_impact**: JSONField(blank=True, default=dict, help_text="Environmental impact metrics, e.g. {'co2_eq_per_ton':..., 'water_use_m3_per_ton':...}")
- **required_materials**: ManyToManyField to `materials.models.Material` through `RequiredMaterial` (fields: `quantity`, `unit`); input materials for the process type.
- **pollutant_emissions**: ManyToManyField to `materials.models.Material` through `PollutantEmission` (fields: `emission_rate`, `unit`); pollutants are `Material` instances distinguished by category/tags.

### 3.3 Data Modeling Guidelines
- **Fixed-schema fields** (e.g., mechanism, temperature_min/max, capacity_min/max, residence_time_min/max, yield_percentage, pressure_min/max, capital_cost, operating_cost): model as explicit Django fields to ensure type safety, DB constraints (e.g. CHECK), and efficient filtering/indexing.
- **JSONField usage**: reserve for truly variable or free-form data you rarely filter on (e.g., `default_parameters` on `ProcessType`, `parameters` on `Process`, `config` on `ProcessStep`).
- **Metrics JSON** (`energy_consumption`, `environmental_impact`): acceptable as JSON if you treat these as opaque blobs; if you later need to query or report by individual metric keys, migrate them into relational models or explicit columns.
- **Future migration**: consider through-models (e.g., `RequiredMaterial`, `EmissionMetric`) for any JSON data you need to sort, filter, or enforce referential integrity on.

## 4. Services Layer
- `conversion.py`  
  - `run_process(process_id)`  
    - validate inputs, fetch parameters  
    - apply step logic  
    - record output, status

## 5. API & Routing

- **ProcessType endpoints**  
  - `GET /api/process-types/`  
    - filters:  
      - `?input_material=<material_id>` → list types compatible by input  
      - `?output_material=<material_id>` → list types producing specified material

- **Process run endpoints**  
  - `POST /api/processes/{process_type_id}/run/` → start a Process run  
  - `GET /api/processes/` → list past runs (filters: input_material, output_material)

- **Alternatives endpoint**  
  - `GET /api/process-types/alternatives/?process_codes=<code1,code2>`  
    → list alternative output materials and process types for given codes

Use DRF `ModelViewSet` for `ProcessTypeViewSet` and `ProcessViewSet`, with custom `@action`s for `run` and `alternatives`.

## 6. Admin
- Register ProcessType, Process, ProcessStep  
- Inline steps under Process

## 7. Integration & Settings
- Add `"processes.apps.ProcessesConfig"` to `INSTALLED_APPS`  
- Include `processes.urls` in project `urls.py`:
  ```python
  path("api/processes/", include("processes.urls"))
  ```
### 7.1 Integration with Materials app
- Use `materials.models.Material` for `Process.input_material` and `Process.output_material`.
- Use existing `MaterialCategory` for material-process compatibility; link via `ProcessCompatibility`.
- Import `Material` and `MaterialCategory` in `processes.models`.
- In API serializers, include material fields or IDs to reference materials when creating/running processes.

### 7.2 Integration with Utils App
- **Base model mixins**: Subclass `utils.models.NamedUserCreatedObject` (which includes `CRUDUrlsMixin`, `CommonInfo`) for `ProcessCategory`, `ProcessType`, `Process`, `ProcessStep` to inherit owner, publication_status, timestamps, and URL helpers.
- **API viewsets**: Use `utils.viewsets.AutoPermModelViewSet` for `ProcessTypeViewSet` and `ProcessViewSet` to auto-generate permissions and standard CRUD actions.
- **Filtering**: Leverage `utils.filters.NullableRangeFilter`, `NullablePercentageRangeFilter`, and `CrispyAutocompleteFilterSet` to build DRF or Django-filter filters for metadata fields (temperature, capacity, yield, etc.) and material/category selectors.
- **Forms & Widgets**: In Django admin or custom forms, use `utils.forms.ModalModelForm` and `utils.widgets.RangeSliderWidget` (or `NullableRangeSliderWidget`) for user-friendly input of range fields.
- **File export**: Integrate `utils.file_export` views and renderers to enable exporting process definitions and compatibility tables to CSV/XLSX.
- **Template tags**: Utilize `utils.templatetags` (e.g., `options_list_url`) in templates or front-end code for generating URLs and option lists dynamically.

### 7.3 Integration & Dependencies
- **Dependencies**:
  - **Utils**: core mixins, viewsets, filters, forms, widgets, and file export (`utils.file_export`); Utils remains standalone.
  - **Materials**: import `Material` and `MaterialCategory` for I/O definitions and compatibility logic; Materials remains standalone.
  - **Sources**: link `ProcessType.sources` to `bibliography.models.Source` for documentation; bibliography remains standalone.
  - **Maps**: optional spatial tagging of `Process`/`ProcessType` and integration with `maps` serializers/views; Maps remains standalone.
- **Dependents**:
  - **Case Studies**: `case_studies.*` apps may consume Processes APIs for scenario workflows; Processes does not depend on any case study.

## 8. Testing Strategy
- **Models**: field constraints, FK relations  
- **Services**: success, failure, edge cases  
- **API**: CRUD + run endpoint with `--keepdb --noinput`

## 9. Migrations & Deployment
- Generate initial migrations  
- Add to CI pipeline (tests, lint)  
- Document any ENV variables (e.g. for heavy conversions)

## 10. Next Steps
### Phase I: Core MVP
1. Create UI mockup/wireframe for stakeholder review and discussion
2. Scaffold `processes` app via `python manage.py startapp processes`
3. Define models & migrations:
   - explicit fields for fixed-schema metadata
   - through-models (`RequiredMaterial`, `PollutantEmission`)
   - JSONFields for free-form `default_parameters`, `parameters`, `config`
4. Implement serializers, viewsets (using `AutoPermModelViewSet`), URLs, and admin registration
5. Implement run endpoint (`POST /api/processes/{id}/run/`) and core conversion logic
6. Write unit tests (models, API) and iterate

### Phase II: Semantic Integration
7. Add optional `ontology_uri` (URLField) to `ProcessCategory`/`ProcessType` for external IRIs
8. Create `processes-context.json` for JSON-LD context and configure DRF JSON-LD/Hydra renderer
9. Expose `/api/ontology-mappings/` endpoint to publish local→external term mappings
10. Align class/field names (or proxy models) with OntoCAPE vocabulary

### Future Enhancements
- Publish SKOS/TTL mapping files and validate against OntoCAPE via PySHACL
- Link `RequiredMaterial` and `PollutantEmission` to ChEBI/ENVO IRIs
- Achieve full Linked-Data compliance with JSON-LD/Hydra

---
*End of Working Plan*

# File Export URL Flow (Updated)

## Overview
This document explains how the file export URL is constructed and used in the BRIT application, from template to backend view, including all key code references.

---

## 1. Template Tag Usage
- In templates (e.g., `waste_collection_map.html`, `collection_filter.html`), the export modal is triggered using:
  ```django
  {% export_link_modal 'collection-export' %}
  ```
- This tag is defined in `utils/file_export/templatetags/file_export_tags.py` as `export_link_modal`.
- It generates a URL for the export modal, e.g.:
  ```
  /utils/file_export/export-modal/?export_url=/waste_collection/collections/export/
  ```

## 2. Generalized Parameter Passing

- When triggering the export modal, use the `export_link_modal` template tag and pass any required parameters as keyword arguments.
- All such parameters are included as query parameters in the modal URL.
- The modal view adds all these parameters to the template context (except `export_url`).
- The export modal template uses these as data attributes on the export buttons.
- The export JavaScript reads these data attributes and includes them as query parameters in the export request.
- The backend export view receives all parameters in `request.GET` and uses them for filtering.

### Example

```django
{% export_link_modal 'collection-export' list_type=list_type foo=bar %}
```
- Results in modal URL:
  `/utils/file_export/export-modal/?export_url=/waste_collection/collections/export/&list_type=private&foo=bar`
- Results in export button:
  `data-list-type="private" data-foo="bar"`
- Results in export request:
  `/waste_collection/collections/export/?format=csv&list_type=private&foo=bar`

## 3. Frontend JavaScript
- The modal renders export format buttons (CSV, XLSX) with `data-export-url` attributes.
- When a user clicks a button, `file_export.js` uses `prepare_export(format)`:
  - Takes the base export URL from `data-export-url`.
  - Appends all current filter query parameters from the list view URL, ensuring the export matches the user's current filtered list.
  - Adds the selected format, e.g.:
    `/waste_collection/collections/export/?format=csv&catchment=1`
- This URL is used to start the export process via AJAX.

## 4. Backend View
- The export URL (e.g. `/waste_collection/collections/export/`) is handled by a Django class-based view (e.g., `CollectionListFileExportView`).
- This view starts a background task to generate the file and returns a task ID for progress monitoring.

---

## Notes
- This system is fully general for any number of extra parameters or filters.
- Debugging logs have been removed from production code.

---

## Code References
- Template tag: `utils/file_export/templatetags/file_export_tags.py` (`export_link_modal`)
- Modal template: `utils/file_export/templates/export_modal_content.html`
- JS: `utils/file_export/static/js/file_export.js` (`prepare_export`, `start_export`)
- Export view: `case_studies/soilcom/views.py` (`CollectionListFileExportView`)

---

## Example
- User clicks export in UI → Modal opens
- User selects format → JS builds URL like `/waste_collection/collections/export/?format=csv&catchment=1`
- AJAX request triggers backend export task
- Progress and download are handled via returned task ID

---

## Troubleshooting
- If export does not work, check:
  - The export URL in the modal (should match the correct Django view)
  - That JS appends the correct query params
  - The backend view is registered and functioning
  - The task ID is returned and used for progress monitoring

---

_Last updated: 2025-05-02_

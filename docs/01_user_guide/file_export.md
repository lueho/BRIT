# Exporting User-Created Objects

This guide describes how to use, extend, and test the generic export workflow for all models derived from `UserCreatedObject`, including Collections and future models. The new export system is secure, DRY, and easy to extend.

---

## How Export Works

- **Export Views:**
  - Each exportable model has a dedicated export view, subclassing `GenericUserCreatedObjectExportView`.
  - The view sets `model_label` (e.g., `'soilcom.Collection'`).
  - The view automatically determines which objects the user can export (published or owned) and passes filter parameters and context (such as `user_id` and `list_type`) to the export task. No long lists of IDs are passed.

- **Export Task:**
  - The generic Celery task receives the model label, filter parameters, and context (e.g., user ID, list type).
  - It loads the correct model, filterset, serializer, and renderer from the export registry.
  - It reconstructs the queryset using the context (e.g., published/owned restriction), applies filters, serializes, and renders the export file.

- **Registry:**
  - All exportable models must be registered in `utils/file_export/registry_init.py`.

---

## How to Register a New Model for Export

1. **Create/Reuse FilterSet, Serializer, and Renderer** for your model.
2. **Register in the export registry** (`utils/file_export/registry_init.py`):

```python
register_export(
    'myapp.MyModel',
    MyModelFilterSet,
    MyModelFlatSerializer,
    {'xlsx': MyModelXLSXRenderer, 'csv': MyModelCSVRenderer}
)
```
3. **Create a view** for export:

```python
from utils.file_export.views import GenericUserCreatedObjectExportView

class MyModelListFileExportView(GenericUserCreatedObjectExportView):
    model_label = 'myapp.MyModel'
```

4. **Add a URL pattern** pointing to your new view.

---

## Passing Filters and Parameters to Export

The export functionality supports passing any filter or context parameter from your current view to the export modal and export task.

- When rendering the export modal link, use the `export_link_modal` template tag and pass any required parameters as keyword arguments:
  
  ```django
  {% export_link_modal 'collection-export' list_type=list_type foo=bar %}
  ```
- All parameters passed this way will be available in the export modal context and as data attributes on the export buttons.
- The export JavaScript will include these parameters as query parameters in the export request.
- The backend view will receive these parameters in `request.GET` and use them in filtering logic, ensuring the export matches the current filtered view.

### Example Workflow

1. User opens a filtered list (e.g., private collections) and clicks Export.
2. The export modal is triggered with the correct parameters in the URL (e.g., `list_type=private`).
3. The export modal buttons include these as data attributes (e.g., `data-list-type="private"`).
4. The export request includes all parameters as query params.
5. The backend view uses these parameters to filter the exported data.

This approach is fully general and supports any number of extra parameters or filters.

---

## Security and Consistency

- The export task always reconstructs the queryset using the passed context (e.g., user ID, list type) and applies all filters, ensuring exports match what the user is allowed to see.
- No sensitive or unnecessary data is passed to Celery.
- If objects are deleted between export start and finish, they will simply be missing from the export (consistent with filtered list views).

---

## Migrating Legacy Exports

- If you are migrating an old export, remove any code that passes or expects lists of IDs.
- Update your export views and tasks to use filter parameters and context instead.

---

## Troubleshooting
- If you get an error about missing registry entry, make sure your model is registered in `registry_init.py`.
- If the export file is empty, check your filter logic and filters.
- For permission issues, ensure the view is subclassing `GenericUserCreatedObjectExportView` and your model has `owner` and `publication_status` fields.

---

## Advanced
- For very large exports, consider batching or streaming if needed (not yet implemented).

---

## Questions?
- For implementation details, see `utils/file_export/README.md` and the code in `utils/file_export/`.
- Contact the engineering team for further help.

---

*Last updated: 2025-05-05. This documentation reflects the current, production-ready export workflow.*

# File Export Package

This package provides functionality for exporting data from filtered model lists to various file formats.

## Overview

The file_export package enables asynchronous export of filtered data to different file formats (CSV, XLSX) using Celery for background processing. Exported files are temporarily stored in an S3 bucket for download.

## Components

### Views

#### FilteredListFileExportView

A base view for exporting filtered model data to a file.

```python
from utils.file_export.views import FilteredListFileExportView

class MyModelExportView(FilteredListFileExportView):
    task_function = my_export_task
    
    def get_filter_params(self, request, params):
        # Custom filter parameter processing
        return processed_params
```

#### ExportModalView

A view to render the export modal content for dynamic loading.

```python
from utils.file_export.views import ExportModalView

# In urls.py
path('export-modal/', ExportModalView.as_view(), name='export_modal'),
```

#### FilteredListFileExportProgressView

A view to check the progress of an export task.

```python
from utils.file_export.views import FilteredListFileExportProgressView

# In urls.py
path('export-progress/<str:task_id>/', FilteredListFileExportProgressView.as_view(), name='export_progress'),
```

### Renderers

#### BaseXLSXRenderer

A base class for rendering data to Excel XLSX files.

```python
from utils.file_export.renderers import BaseXLSXRenderer

class MyModelXLSXRenderer(BaseXLSXRenderer):
    labels = {
        'id': 'ID',
        'name': 'Name',
        'description': 'Description',
    }
    column_order = ['id', 'name', 'description']
```

#### BaseCSVRenderer

A base class for rendering data to CSV files.

```python
from utils.file_export.renderers import BaseCSVRenderer

class MyModelCSVRenderer(BaseCSVRenderer):
    labels = {
        'id': 'ID',
        'name': 'Name',
        'description': 'Description',
    }
    header = ['id', 'name', 'description']
```

### Storage

#### TempUserFileDownloadStorage

A storage class that extends S3Boto3Storage to store files in a temporary location in an S3 bucket.

```python
from utils.file_export.storages import TempUserFileDownloadStorage

storage = TempUserFileDownloadStorage()
```

#### write_file_for_download

A function that writes data to a file using a renderer and returns the URL to the file.

```python
from utils.file_export.storages import write_file_for_download
from myapp.renderers import MyModelCSVRenderer

url = write_file_for_download('mymodel_export.csv', data, MyModelCSVRenderer)
```

## Usage Example

### Creating a Celery Task for Export

```python
from celery import shared_task
from utils.file_export.storages import write_file_for_download
from myapp.renderers import MyModelCSVRenderer, MyModelXLSXRenderer

@shared_task
def export_my_model_data(file_format, filter_params):
    # Query the data based on filter_params
    queryset = MyModel.objects.filter(**filter_params)
    data = [{'id': obj.id, 'name': obj.name, 'description': obj.description} for obj in queryset]
    
    # Choose the renderer based on the file format
    if file_format == 'xlsx':
        renderer_class = MyModelXLSXRenderer
        file_name = 'mymodel_export.xlsx'
    else:  # Default to CSV
        renderer_class = MyModelCSVRenderer
        file_name = 'mymodel_export.csv'
    
    # Write the file and get the download URL
    url = write_file_for_download(file_name, data, renderer_class)
    
    return {'download_url': url}
```

### Setting Up the Export View

```python
from utils.file_export.views import FilteredListFileExportView
from myapp.tasks import export_my_model_data

class MyModelExportView(FilteredListFileExportView):
    task_function = export_my_model_data
```

### Adding URLs

```python
from django.urls import path
from utils.file_export.views import FilteredListFileExportProgressView, ExportModalView
from myapp.views import MyModelExportView

urlpatterns = [
    path('export/', MyModelExportView.as_view(), name='export_my_model'),
    path('export-progress/<str:task_id>/', FilteredListFileExportProgressView.as_view(), name='export_progress'),
    path('export-modal/', ExportModalView.as_view(), name='export_modal'),
]
```

## Dependencies

The file_export package depends on:

1. **Python**:
   - django
   - celery
   - xlsxwriter
   - djangorestframework-csv
   - django-storages
   - boto3

2. **Templates**:
   - export_modal_content.html

## Files

- `views.py`: Contains the views for handling export requests and checking export progress
- `renderers.py`: Contains the renderer classes for different file formats
- `storages.py`: Contains the storage class and utility function for storing exported files
- `urls.py`: Contains the URL patterns for the export views
- `apps.py`: Contains the app configuration
# Utils App

The Utils app provides a collection of reusable components, utilities, and base classes for the BRIT (Bioresource Inventory Tool) project.

## Overview

The Utils app serves as a foundation for other apps in the project, offering common functionality such as:

- Base models for user-created objects
- CRUD views with permission handling
- Custom form fields and widgets
- File export capabilities
- Property management
- Template tags and filters
- And more

## Packages

The Utils app is organized into several packages:

### Fields

The [Fields package](fields/README.md) provides custom field classes for use with Django forms and crispy forms, such as:

- `ForeignkeyField`: A field for selecting a model instance with a button to create a new instance through a modal form
- `NullableRangeField`: A field for selecting a range of values with an option to include null values
- `NullablePercentageRangeField`: A specialized version of NullableRangeField for percentage values

### Widgets

The [Widgets package](widgets/README.md) contains custom widget classes for use with Django forms, including:

- `RangeSliderWidget`: A widget for selecting a range of values using a slider interface
- `NullableRangeSliderWidget`: A widget that extends RangeSliderWidget to include null values
- `NullablePercentageRangeSliderWidget`: A specialized version of NullableRangeSliderWidget for percentage values
- Bootstrap-styled Select2 widgets for autocomplete functionality

### File Export

The [File Export package](file_export/README.md) provides functionality for exporting data from filtered model lists to various file formats:

- Views for handling export requests and checking export progress
- Renderers for different file formats (CSV, XLSX)
- Storage utilities for storing exported files

### Properties

The [Properties package](properties/README.md) enables the definition of properties that can be shared among different models:

- Models for units, properties, and property values
- Views for managing properties and units
- Forms for creating and updating properties and units

### Template Tags

The [Template Tags package](templatetags/README.md) provides custom template tags and filters for use in Django templates:

- Filters for working with user-created objects
- Other utility functions for templates

## Core Components

### Models

The Utils app provides several base models that can be used by other apps:

#### CRUDUrlsMixin

A mixin that provides URL generation methods for CRUD operations.

```python
from utils.models import CRUDUrlsMixin

class MyModel(CRUDUrlsMixin, models.Model):
    name = models.CharField(max_length=255)
    
    # The mixin provides methods like:
    # get_absolute_url()
    # get_update_url()
    # get_delete_url()
    # etc.
```

#### GlobalObject

A base model for globally accessible objects.

```python
from utils.models import GlobalObject

class MyGlobalModel(GlobalObject):
    name = models.CharField(max_length=255)
```

#### UserCreatedObject

A base model for objects created by users with publication status.

```python
from utils.models import UserCreatedObject

class MyUserCreatedModel(UserCreatedObject):
    name = models.CharField(max_length=255)
```

#### NamedUserCreatedObject

An extension of UserCreatedObject with a name field.

```python
from utils.models import NamedUserCreatedObject

class MyNamedUserCreatedModel(NamedUserCreatedObject):
    # The name field is already provided by NamedUserCreatedObject
    description = models.TextField()
```

### Views

The Utils app provides several base views that can be used by other apps:

#### List Views

- `PublishedObjectListView`: A list view for published objects
- `PrivateObjectListView`: A list view for private objects
- `FilterView` variants: List views with filtering capabilities

#### CRUD Views

- `UserCreatedObjectCreateView`: A create view for user-created objects
- `UserCreatedObjectDetailView`: A detail view for user-created objects
- `UserCreatedObjectUpdateView`: An update view for user-created objects
- `UserCreatedObjectDeleteView`: A delete view for user-created objects

#### Modal Views

- Modal versions of CRUD operations for use with Bootstrap Modal Forms

#### Access Control Mixins

- `UserCreatedObjectReadAccessMixin`: A mixin for controlling read access to user-created objects
- `UserCreatedObjectWriteAccessMixin`: A mixin for controlling write access to user-created objects

#### Utility Views

- `ModelSelectOptionsView`: A view for providing options for select fields
- `DynamicRedirectView`: A view for handling dynamic redirects

### Forms

The Utils app provides several base forms that can be used by other apps:

#### Base Forms

- `SimpleForm`: A base form with common functionality
- `SimpleModelForm`: A base model form with common functionality

#### Modal Forms

- `ModalForm`: A form for use with Bootstrap Modal Forms
- `ModalModelForm`: A model form for use with Bootstrap Modal Forms

#### Autocomplete Forms

- `AutoCompleteForm`: A form with autocomplete functionality
- `AutoCompleteModelForm`: A model form with autocomplete functionality

#### Formset Helpers

- `DynamicTableInlineFormSetHelper`: A helper for dynamic inline formsets

#### M2M Formsets

- `M2MInlineFormSet`: A formset for many-to-many relationships
- `M2MInlineModelFormSet`: A model formset for many-to-many relationships

### Filters

The Utils app provides several filter classes for use with django-filter:

#### Base Filter Sets

- `BaseCrispyFilterSet`: A base filter set with Crispy Forms integration
- `CrispyAutocompleteFilterSet`: A filter set with autocomplete functionality

#### Custom Filters

- `NullableRangeFilter`: A filter for ranges that can include null values
- `NullablePercentageRangeFilter`: A specialized range filter for percentages

## Usage Examples

### Creating a User-Created Model

```python
from utils.models import NamedUserCreatedObject

class MyModel(NamedUserCreatedObject):
    description = models.TextField()
    
    def __str__(self):
        return self.name
```

### Creating CRUD Views for a User-Created Model

```python
from utils.views import (
    PublishedObjectListView, PrivateObjectListView,
    UserCreatedObjectCreateView, UserCreatedObjectDetailView,
    UserCreatedObjectUpdateView, UserCreatedObjectDeleteView
)
from myapp.models import MyModel
from myapp.forms import MyModelForm

class MyModelPublishedListView(PublishedObjectListView):
    model = MyModel

class MyModelPrivateListView(PrivateObjectListView):
    model = MyModel

class MyModelCreateView(UserCreatedObjectCreateView):
    model = MyModel
    form_class = MyModelForm

class MyModelDetailView(UserCreatedObjectDetailView):
    model = MyModel

class MyModelUpdateView(UserCreatedObjectUpdateView):
    model = MyModel
    form_class = MyModelForm

class MyModelDeleteView(UserCreatedObjectDeleteView):
    model = MyModel
```

### Creating a Filter Set for a Model

```python
from utils.filters import BaseCrispyFilterSet
from django_filters import CharFilter
from myapp.models import MyModel

class MyModelFilterSet(BaseCrispyFilterSet):
    name = CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = MyModel
        fields = ['name']
```

## Dependencies

The Utils app depends on:

1. **Python**:
   - django
   - django-crispy-forms
   - django-filter
   - django-autocomplete-light
   - django-bootstrap-modal-forms
   - xlsxwriter
   - djangorestframework-csv
   - django-storages
   - boto3

2. **JavaScript**:
   - jQuery
   - jQuery UI
   - Bootstrap
   - Select2

## Files

- `models.py`: Contains the base models
- `views.py`: Contains the base views
- `forms.py`: Contains the base forms
- `filters.py`: Contains the filter classes
- `widgets.py`: Contains the widget classes
- `fields.py`: Contains the field classes
- `crispy_fields.py`: Contains the crispy form field classes
- `permissions.py`: Contains permission classes and utilities
- `serializers.py`: Contains serializer classes for the REST API
- `viewsets.py`: Contains viewset classes for the REST API
- `urls.py`: Contains URL patterns for the Utils app
- `exceptions.py`: Contains custom exceptions
- `apps.py`: Contains the app configuration
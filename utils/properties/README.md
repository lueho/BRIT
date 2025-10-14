# Properties Package

This package provides functionality for defining and managing properties and their values, with support for different units of measurement.

## Overview

The properties package enables the definition of properties that can be shared among different models, allowing for comparison of instances of different models that share the same properties while enforcing the use of matching units.

## Models

### Unit

The `Unit` model represents a unit of measurement.

```python
from utils.properties.models import Unit

# Create a unit
unit = Unit.objects.create(
    owner=request.user,
    name='Kilogram',
    dimensionless=False
)
```

#### Fields

- `name`: The name of the unit
- `dimensionless`: Whether the unit is dimensionless
- `reference_quantity`: A reference to a Property that this unit measures

### Property

The `Property` model defines properties that can be shared among other models.

```python
from utils.properties.models import Property, Unit

# Create a property
property = Property.objects.create(
    owner=request.user,
    name='Weight',
    unit='kg'
)

# Add allowed units
property.allowed_units.add(Unit.objects.get(name='Kilogram'))
property.allowed_units.add(Unit.objects.get(name='Gram'))
```

#### Fields

- `name`: The name of the property
- `unit`: The default unit for the property
- `allowed_units`: A many-to-many relationship to Unit objects that are allowed for this property

### PropertyValue

The `PropertyValue` model is an abstract base class for linking property definitions to concrete instances with values.

```python
from django.db import models
from utils.properties.models import PropertyValue

class MyModelPropertyValue(PropertyValue):
    my_model = models.ForeignKey('MyModel', on_delete=models.CASCADE, related_name='property_values')
```

#### Fields

- `property`: A foreign key to the Property being measured
- `unit`: A foreign key to the Unit used for the measurement
- `average`: The average value of the measurement
- `standard_deviation`: The standard deviation of the measurement (optional)

## Views

### Dashboard

- `PropertiesDashboardView`: A dashboard view for the properties app

### Unit CRUD

- `UnitPublishedListView`: List view for published units
- `UnitPrivateListView`: List view for private units
- `UnitCreateView`: Create view for units
- `UnitDetailView`: Detail view for units
- `UnitUpdateView`: Update view for units
- `UnitModalDeleteView`: Modal delete view for units

### Property CRUD

- `PropertyPublishedListView`: List view for published properties
- `PropertyPrivateListView`: List view for private properties
- `PropertyCreateView`: Create view for properties
- `PropertyDetailView`: Detail view for properties
- `PropertyUpdateView`: Update view for properties
- `PropertyModalDeleteView`: Modal delete view for properties

### Other Views

- `PropertyUnitOptionsView`: View for getting the allowed units for a property

## Forms

- `PropertyModelForm`: Form for creating and updating Property objects
- `UnitModelForm`: Form for creating and updating Unit objects

## Usage Example

### Creating a Model with Properties

```python
from django.db import models
from utils.properties.models import PropertyValue

class MyModel(models.Model):
    name = models.CharField(max_length=255)
    
    def __str__(self):
        return self.name

class MyModelPropertyValue(PropertyValue):
    my_model = models.ForeignKey(MyModel, on_delete=models.CASCADE, related_name='property_values')
```

### Adding Properties to a Model Instance

```python
from utils.properties.models import Property, Unit
from myapp.models import MyModel, MyModelPropertyValue

# Create a model instance
my_model = MyModel.objects.create(name='Example')

# Create a property
weight_property = Property.objects.create(
    owner=request.user,
    name='Weight',
    unit='kg'
)

# Create a unit
kg_unit = Unit.objects.create(
    owner=request.user,
    name='Kilogram',
    dimensionless=False
)

# Add the unit to the property's allowed units
weight_property.allowed_units.add(kg_unit)

# Create a property value for the model instance
MyModelPropertyValue.objects.create(
    owner=request.user,
    name='Weight measurement',
    property=weight_property,
    unit=kg_unit,
    average=75.5,
    standard_deviation=0.5,
    my_model=my_model
)
```

### Querying Models by Property Values

```python
from myapp.models import MyModel, MyModelPropertyValue
from utils.properties.models import Property

# Get the property
weight_property = Property.objects.get(name='Weight')

# Get all models with a weight property value greater than 70
heavy_models = MyModel.objects.filter(
    property_values__property=weight_property,
    property_values__average__gt=70
)
```

## Dependencies

The properties package depends on:

1. **Python**:
   - django
   - utils.models (NamedUserCreatedObject, get_default_owner)
   - utils.views (OwnedObjectCreateView, etc.)

2. **Templates**:
   - properties_dashboard.html

## Files

- `models.py`: Contains the models for units, properties, and property values
- `views.py`: Contains the views for managing properties and units
- `forms.py`: Contains the forms for creating and updating properties and units
- `urls.py`: Contains the URL patterns for the properties app
- `admin.py`: Contains the admin configuration for the properties app
- `apps.py`: Contains the app configuration
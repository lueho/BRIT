# Template Tags Package

This package provides custom template tags and filters for use in Django templates.

## Overview

The template tags package includes filters for working with user-created objects and other utility functions for templates.

## Template Tags and Filters

### User Created Object Tags

The `user_created_object_tags.py` module provides tags and filters for working with user-created objects.

#### is_user_created

A filter that checks if a model class is user-created.

```python
{% load user_created_object_tags %}

{% if model_class|is_user_created %}
    <!-- This model is user-created -->
{% else %}
    <!-- This model is not user-created -->
{% endif %}
```

## Usage Example

### In Templates

```html
{% load user_created_object_tags %}

<ul>
{% for model_class in model_classes %}
    <li>
        {{ model_class.name }}
        {% if model_class|is_user_created %}
            <span class="badge badge-info">User Created</span>
        {% endif %}
    </li>
{% endfor %}
</ul>
```

### In Views

```python
from django.views.generic import TemplateView
from myapp.models import MyModel, AnotherModel

class ModelListView(TemplateView):
    template_name = 'model_list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_classes'] = [MyModel, AnotherModel]
        return context
```

## Dependencies

The template tags package depends on:

1. **Python**:
   - django

## Files

- `user_created_object_tags.py`: Contains template tags and filters for working with user-created objects
- `__init__.py`: Empty file to make the directory a Python package
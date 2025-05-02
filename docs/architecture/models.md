# Models and Data Structures

This section documents the core data models and relationships in BRIT.

---

## Main Models
- Each Django app defines its own models in `<app>/models.py`.
- Models are managed via Django ORM and synced to PostgreSQL/PostGIS.

## Entity-Relationship Diagram
- (To generate: use `django-extensions graph_models` or similar tool)

## Example Model: User
```python
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Custom fields here
    pass
```

## Example Model: Map
```python
from django.db import models

class Map(models.Model):
    name = models.CharField(max_length=255)
    geometry = models.GeometryField()
    created_at = models.DateTimeField(auto_now_add=True)
```

## Extending Models
- Add new fields or relationships as needed
- Use migrations to update the database schema

---

_Last updated: 2025-05-02_

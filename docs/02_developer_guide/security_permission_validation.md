# Permission Validation Architecture

## Overview

BRIT implements a **defense-in-depth** approach to permission validation for user-created objects, combining frontend UX filtering with backend security validation.

## Components

### 1. Frontend: Autocomplete Filtering (UX)

**Location**: Autocomplete views (`UserCreatedObjectAutocompleteView`)

**Purpose**: Filter dropdown options in UI based on user permissions

**Example**:
```python
class SourceAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Source
    
    def hook_queryset(self, queryset):
        # Filter to only show sources user can access
        return filter_queryset_for_user(queryset, self.request.user)
```

**Benefits**:
- Improved UX (users only see relevant options)
- Reduced bandwidth (smaller option lists)
- Performance optimization

**Limitation**: ⚠️ Can be bypassed via browser devtools or direct POST requests

---

### 2. Backend: Form Validation (Security)

**Location**: Form `clean()` methods via `UserCreatedObjectFormMixin`

**Purpose**: Validate that user has permission to access selected objects

**Implementation**:
```python
class UserCreatedObjectFormMixin:
    def clean(self):
        cleaned_data = super().clean()
        request = getattr(self, 'request', None)
        
        # Check all UserCreatedObject fields
        for field_name, value in cleaned_data.items():
            if isinstance(value, UserCreatedObject):
                # Validate permission using existing permission system
                filtered_qs = filter_queryset_for_user(
                    value.__class__.objects.filter(pk=value.pk),
                    request.user
                )
                if not filtered_qs.exists():
                    raise ValidationError(...)
        
        return cleaned_data
```

**Benefits**:
- ✅ **Cannot be bypassed** - runs on server
- ✅ **Consistent** - applies to all UserCreatedObject fields automatically
- ✅ **Centralized** - single source of truth for validation logic
- ✅ **Comprehensive** - validates both ForeignKey and M2M relationships

---

## Usage

### For Forms with UserCreatedObject References

```python
from utils.forms import UserCreatedObjectFormMixin, SimpleModelForm

class MyModelForm(UserCreatedObjectFormMixin, SimpleModelForm):
    # TomSelect fields with autocomplete
    catchment = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="catchment-autocomplete",  # ← Frontend filtering
            label_field="name",
        ),
    )
    
    class Meta:
        model = MyModel
        fields = ('name', 'catchment', ...)
```

**In the View**:
```python
class MyCreateView(UserCreatedObjectCreateView):
    form_class = MyModelForm
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request  # ← Required for validation
        return kwargs
```

### For Sources Field (Special Case)

The sources field uses an additional mixin for widget setup:

```python
from utils.forms import UserCreatedObjectFormMixin, SourcesFieldMixin, SimpleModelForm

class MyModelForm(UserCreatedObjectFormMixin, SourcesFieldMixin, SimpleModelForm):
    class Meta:
        model = MyModel
        fields = ('name', 'sources', ...)
```

**What each mixin does**:
- `UserCreatedObjectFormMixin`: Permission validation (security) ✓
- `SourcesFieldMixin`: Widget setup + queryset population (UX) ✓

---

## Security Model

### Permission Rules

Enforced by `filter_queryset_for_user()`:

1. **Public objects**: Accessible to all authenticated users
2. **Private objects**: Only accessible to:
   - Owner
   - Staff/superusers
   - Users with explicit permissions

3. **Review/Draft objects**: Only accessible to:
   - Owner
   - Moderators for that model

### Attack Vectors Prevented

❌ **Browser Devtools Bypass**
```javascript
// Attacker tries to inject unauthorized ID via devtools
fetch('/form/', {
    method: 'POST',
    body: 'catchment=999'  // ID of private catchment they don't own
})
```
✅ **Blocked by**: `UserCreatedObjectFormMixin.clean()` validates ID 999
and raises `ValidationError` if user lacks permission

❌ **Direct POST Request**
```bash
# Attacker tries direct POST without using the form UI
curl -X POST /form/ -d "material=123&sources=456,789"
```
✅ **Blocked by**: Backend validation checks all submitted IDs (123, 456, 789)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    User Submits Form                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  1. FRONTEND (UX Layer)                                 │
│  • TomSelect autocomplete shows filtered options        │
│  • UserCreatedObjectAutocompleteView.hook_queryset()   │
│  • CAN BE BYPASSED via devtools/direct POST             │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  2. FORM VALIDATION (Security Layer)                    │
│  • UserCreatedObjectFormMixin.clean()                   │
│  • Validates ALL UserCreatedObject references           │
│  • Uses filter_queryset_for_user() permission check     │
│  • CANNOT BE BYPASSED - runs on server                  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  3. DATABASE SAVE                                       │
│  • Only objects user has permission to access           │
└─────────────────────────────────────────────────────────┘
```

---

## Migration Guide

### Before (Inconsistent)

```python
# Some forms had permission checks
class SampleModelForm(SimpleModelForm):
    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Manual permission filtering (only for some fields)
        if request:
            queryset = filter_queryset_for_user(
                Source.objects.filter(...), 
                request.user
            )
            self.fields['sources'].queryset = queryset
```

**Problem**: Other fields (material, series, catchment, etc.) had no validation!

### After (Consistent)

```python
# All forms automatically protected
class SampleModelForm(UserCreatedObjectFormMixin, SimpleModelForm):
    # No manual permission code needed!
    # ALL UserCreatedObject fields automatically validated
    pass
```

**Benefits**: Material, series, sources, catchment, collector ALL validated ✓

---

## Testing

### Test Permission Validation

```python
def test_form_rejects_unauthorized_object(self):
    """User cannot select objects they don't have permission for."""
    # Create private object owned by another user
    other_user = User.objects.create(username='other')
    private_catchment = Catchment.objects.create(
        owner=other_user,
        publication_status='private',
        name='Private Catchment'
    )
    
    # Try to submit form with unauthorized catchment
    form = CollectionModelForm(
        data={'catchment': private_catchment.id, ...},
        request=self.request  # Current user
    )
    
    # Form should be invalid
    self.assertFalse(form.is_valid())
    self.assertIn('catchment', form.errors)
    self.assertIn("don't have permission", str(form.errors['catchment']))
```

---

## Performance Considerations

### Queryset Optimization

The mixin checks each object individually, which could cause N+1 queries. However:

1. **Small scale**: Forms typically have < 10 UserCreatedObject fields
2. **Caching**: Permission checks use Django's query caching
3. **Efficient**: `filter_queryset_for_user()` uses optimized queries

### If Performance Becomes an Issue

```python
# Option: Prefetch all permission data in view
def get_form_kwargs(self):
    kwargs = super().get_form_kwargs()
    kwargs['request'] = self.request
    
    # Prefetch related data for permission checks
    if hasattr(self, 'object') and self.object:
        self.object = self.object.select_related(
            'catchment__owner',
            'collector__owner',
            'material__owner'
        )
    return kwargs
```

---

## Summary

| Aspect | Frontend (Autocomplete) | Backend (Mixin) |
|--------|-------------------------|-----------------|
| **Purpose** | UX filtering | Security validation |
| **Location** | Autocomplete view | Form.clean() |
| **Can be bypassed?** | ✗ Yes (devtools) | ✓ No (server-side) |
| **Applies to** | Dropdown options | All submitted data |
| **When to use** | Always (UX) | Always (security) |
| **Implementation** | Per autocomplete view | One mixin for all forms |

**Best Practice**: Use BOTH layers for defense-in-depth ✓

# Processes Module - Production Roadmap

## Current State Analysis

### ✅ Complete Components
- **Models** (7 models with comprehensive validation)
  - Process, ProcessCategory, ProcessMaterial, ProcessOperatingParameter
  - ProcessLink, ProcessInfoResource, ProcessReference
- **Admin Interface** (fully configured with inlines)
- **Tests** (39 model tests, all passing)
- **URL Routing** (basic mock views only)
- **Templates** (mock/demo templates exist)

### ❌ Missing Components
- CRUD Views for production use
- Forms for data input
- Filters for list views
- Serializers & ViewSets for API
- Production templates
- View tests
- Form tests
- Integration tests

---

## Transformation Plan

Based on analysis of the **soilcom** module (most developed) and **materials** module patterns, here's the step-by-step roadmap:

---

## Phase 1: Foundation (Forms & Filters)

### 1.1 Create Forms Module (`forms.py`)

**Priority: HIGH** - Required for all CRUD operations

```python
# processes/forms.py

from crispy_forms.helper import FormHelper
from django import forms
from .models import (
    Process, ProcessCategory, ProcessMaterial, 
    ProcessOperatingParameter, ProcessLink,
    ProcessInfoResource, ProcessReference
)

# Standard Forms
class ProcessCategoryModelForm(forms.ModelForm):
    class Meta:
        model = ProcessCategory
        fields = ['name', 'description', 'publication_status']

class ProcessCategoryModalModelForm(ProcessCategoryModelForm):
    # For modal dialogs - simplified version
    pass

class ProcessModelForm(forms.ModelForm):
    class Meta:
        model = Process
        fields = [
            'name', 'parent', 'categories', 'short_description',
            'mechanism', 'description', 'image', 'publication_status'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        # Add crispy forms configuration

class ProcessModalModelForm(ProcessModelForm):
    # Simplified for quick-add in modals
    class Meta(ProcessModelForm.Meta):
        fields = ['name', 'categories', 'short_description']

# Inline Forms for related objects
class ProcessMaterialInlineFormSet(forms.ModelForm):
    # For managing materials in process creation/update
    pass

class ProcessOperatingParameterInlineFormSet(forms.ModelForm):
    # For managing parameters in process creation/update
    pass
```

**Files to create:**
- `processes/forms.py` (~400-500 lines based on soilcom pattern)

**Pattern reference:** `case_studies/soilcom/forms.py`, `materials/forms.py`

---

### 1.2 Create Filters Module (`filters.py`)

**Priority: MEDIUM** - Needed for list views with search/filter

```python
# processes/filters.py

import django_filters
from .models import Process, ProcessCategory

class ProcessFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Process Name'
    )
    categories = django_filters.ModelMultipleChoiceFilter(
        queryset=ProcessCategory.objects.all(),
        label='Categories'
    )
    mechanism = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Mechanism'
    )
    
    class Meta:
        model = Process
        fields = ['name', 'categories', 'mechanism', 'publication_status']
```

**Files to create:**
- `processes/filters.py` (~200-300 lines)

**Pattern reference:** `case_studies/soilcom/filters.py`, `materials/filters.py`

---

## Phase 2: CRUD Views Implementation

### 2.1 Create Production Views (`views.py`)

**Priority: HIGH** - Core functionality

Replace current mock views with production CRUD views following the established pattern:

```python
# processes/views.py

from utils.object_management.views import (
    UserCreatedObjectCreateView,
    UserCreatedObjectDetailView,
    UserCreatedObjectUpdateView,
    UserCreatedObjectModalCreateView,
    UserCreatedObjectModalDetailView,
    UserCreatedObjectModalUpdateView,
    UserCreatedObjectModalDeleteView,
    UserCreatedObjectAutocompleteView,
    PublishedObjectListView,
    PrivateObjectListView,
    PublishedObjectFilterView,
    PrivateObjectFilterView,
)

# Dashboard
class ProcessDashboardView(TemplateView):
    template_name = 'processes/dashboard.html'
    # Include statistics, charts, quick actions

# ProcessCategory CRUD
class ProcessCategoryCreateView(UserCreatedObjectCreateView):
    model = ProcessCategory
    form_class = ProcessCategoryModelForm
    
class ProcessCategoryModalCreateView(UserCreatedObjectModalCreateView):
    model = ProcessCategory
    form_class = ProcessCategoryModalModelForm

class ProcessCategoryPublishedListView(PublishedObjectListView):
    model = ProcessCategory
    
class ProcessCategoryPrivateListView(PrivateObjectListView):
    model = ProcessCategory
    
class ProcessCategoryDetailView(UserCreatedObjectDetailView):
    model = ProcessCategory
    
class ProcessCategoryModalDetailView(UserCreatedObjectModalDetailView):
    model = ProcessCategory
    
class ProcessCategoryUpdateView(UserCreatedObjectUpdateView):
    model = ProcessCategory
    form_class = ProcessCategoryModelForm
    
class ProcessCategoryModalUpdateView(UserCreatedObjectModalUpdateView):
    model = ProcessCategory
    form_class = ProcessCategoryModalModelForm
    
class ProcessCategoryModalDeleteView(UserCreatedObjectModalDeleteView):
    model = ProcessCategory
    
class ProcessCategoryAutocompleteView(UserCreatedObjectAutocompleteView):
    model = ProcessCategory

# Process CRUD (with inline formsets)
class ProcessCreateView(UserCreatedObjectCreateWithInlinesView):
    model = Process
    form_class = ProcessModelForm
    inlines = [
        ProcessMaterialInline,
        ProcessOperatingParameterInline,
        ProcessLinkInline,
    ]

class ProcessPublishedFilterView(PublishedObjectFilterView):
    model = Process
    filterset_class = ProcessFilter
    
class ProcessPrivateFilterView(PrivateObjectFilterView):
    model = Process
    filterset_class = ProcessFilter

class ProcessDetailView(UserCreatedObjectDetailView):
    model = Process
    # Add context with related data (materials, parameters, etc.)
    
class ProcessUpdateView(UserCreatedObjectUpdateWithInlinesView):
    model = Process
    form_class = ProcessModelForm
    inlines = [...]
    
class ProcessModalDeleteView(UserCreatedObjectModalDeleteView):
    model = Process
    
class ProcessAutocompleteView(UserCreatedObjectAutocompleteView):
    model = Process

# Utility Views
class ProcessAddMaterialView(LoginRequiredMixin, UpdateView):
    # Add material to existing process
    pass

class ProcessAddParameterView(LoginRequiredMixin, UpdateView):
    # Add operating parameter to existing process
    pass
```

**Files to update:**
- `processes/views.py` (~800-1200 lines based on soilcom/materials pattern)

**Pattern reference:** 
- `case_studies/soilcom/views.py` (1204 lines, complex example)
- `materials/views.py` (909 lines, simpler example)

---

### 2.2 Update URL Configuration (`urls.py`)

**Priority: HIGH** - Must match new views

```python
# processes/urls.py

from django.urls import path, include
from . import views
from .router import router  # For API (Phase 4)

app_name = 'processes'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.ProcessDashboardView.as_view(), name='dashboard'),
    
    # ProcessCategory URLs
    path('categories/', views.ProcessCategoryPublishedListView.as_view(), 
         name='processcategory-list'),
    path('categories/user/', views.ProcessCategoryPrivateListView.as_view(),
         name='processcategory-list-owned'),
    path('categories/create/', views.ProcessCategoryCreateView.as_view(),
         name='processcategory-create'),
    path('categories/create/modal/', views.ProcessCategoryModalCreateView.as_view(),
         name='processcategory-create-modal'),
    path('categories/<int:pk>/', views.ProcessCategoryDetailView.as_view(),
         name='processcategory-detail'),
    path('categories/<int:pk>/modal/', views.ProcessCategoryModalDetailView.as_view(),
         name='processcategory-detail-modal'),
    path('categories/<int:pk>/update/', views.ProcessCategoryUpdateView.as_view(),
         name='processcategory-update'),
    path('categories/<int:pk>/update/modal/', views.ProcessCategoryModalUpdateView.as_view(),
         name='processcategory-update-modal'),
    path('categories/<int:pk>/delete/modal/', views.ProcessCategoryModalDeleteView.as_view(),
         name='processcategory-delete-modal'),
    path('categories/autocomplete/', views.ProcessCategoryAutocompleteView.as_view(),
         name='processcategory-autocomplete'),
    
    # Process URLs (similar pattern)
    path('list/', views.ProcessPublishedFilterView.as_view(), name='process-list'),
    path('list/user/', views.ProcessPrivateFilterView.as_view(), name='process-list-owned'),
    path('create/', views.ProcessCreateView.as_view(), name='process-create'),
    path('<int:pk>/', views.ProcessDetailView.as_view(), name='process-detail'),
    path('<int:pk>/update/', views.ProcessUpdateView.as_view(), name='process-update'),
    path('<int:pk>/delete/modal/', views.ProcessModalDeleteView.as_view(), 
         name='process-delete-modal'),
    path('<int:pk>/add-material/', views.ProcessAddMaterialView.as_view(),
         name='process-add-material'),
    path('<int:pk>/add-parameter/', views.ProcessAddParameterView.as_view(),
         name='process-add-parameter'),
    path('autocomplete/', views.ProcessAutocompleteView.as_view(),
         name='process-autocomplete'),
    
    # API endpoints (Phase 4)
    path('api/', include(router.urls)),
]
```

**Files to update:**
- `processes/urls.py` (replace current mock URLs)

---

## Phase 3: Templates

### 3.1 Create Production Templates

**Priority: HIGH** - UI for all CRUD operations

Following the BRIT template structure:

```
processes/templates/processes/
├── dashboard.html                    # Main dashboard
├── processcategory_list.html        # List view
├── processcategory_detail.html      # Detail view
├── processcategory_detail_modal.html # Modal detail
├── processcategory_form.html        # Create/Update form
├── process_list.html                # Filtered list with cards
├── process_detail.html              # Full process detail with tabs
├── process_form.html                # Create/update with inlines
└── partials/
    ├── process_card.html            # Reusable process card
    ├── process_parameters_table.html
    ├── process_materials_table.html
    └── process_links_list.html
```

**Key template features:**
- Use BRIT's base templates
- Include breadcrumbs navigation
- Add filter sidebars for list views
- Include action buttons (edit, delete, duplicate)
- Use modal dialogs for quick actions
- Responsive design with cards/tables
- Include charts/visualizations where appropriate

**Pattern reference:**
- `case_studies/soilcom/templates/` (24 templates)
- `materials/templates/` 
- `utils/object_management/templates/` (base templates)

---

## Phase 4: API Layer (Optional but Recommended)

### 4.1 Create Serializers (`serializers.py`)

**Priority: MEDIUM** - Needed for REST API and data export

```python
# processes/serializers.py

from rest_framework import serializers
from .models import Process, ProcessCategory, ProcessMaterial, ProcessOperatingParameter

class ProcessCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessCategory
        fields = ['id', 'name', 'description', 'publication_status']

class ProcessMaterialSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)
    
    class Meta:
        model = ProcessMaterial
        fields = ['id', 'material', 'material_name', 'role', 'stage', 
                  'stream_label', 'quantity_value', 'quantity_unit', 'optional']

class ProcessOperatingParameterSerializer(serializers.ModelSerializer):
    parameter_display = serializers.CharField(source='get_parameter_display', read_only=True)
    
    class Meta:
        model = ProcessOperatingParameter
        fields = ['id', 'parameter', 'parameter_display', 'name', 'unit',
                  'value_min', 'value_max', 'nominal_value', 'basis']

class ProcessSerializer(serializers.ModelSerializer):
    categories = ProcessCategorySerializer(many=True, read_only=True)
    input_materials = ProcessMaterialSerializer(many=True, read_only=True)
    output_materials = ProcessMaterialSerializer(many=True, read_only=True)
    operating_parameters = ProcessOperatingParameterSerializer(many=True, read_only=True)
    
    class Meta:
        model = Process
        fields = [
            'id', 'name', 'parent', 'categories', 'short_description',
            'mechanism', 'description', 'image', 'input_materials',
            'output_materials', 'operating_parameters', 'publication_status'
        ]
```

**Files to create:**
- `processes/serializers.py` (~300-400 lines)

**Pattern reference:** `case_studies/soilcom/serializers.py`

---

### 4.2 Create ViewSets (`viewsets.py`)

**Priority: MEDIUM** - REST API endpoints

```python
# processes/viewsets.py

from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Process, ProcessCategory
from .serializers import ProcessSerializer, ProcessCategorySerializer

class ProcessCategoryViewSet(viewsets.ModelViewSet):
    queryset = ProcessCategory.objects.filter(publication_status='published')
    serializer_class = ProcessCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']

class ProcessViewSet(viewsets.ModelViewSet):
    queryset = Process.objects.filter(publication_status='published')
    serializer_class = ProcessSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'short_description', 'mechanism']
    
    @action(detail=True, methods=['get'])
    def materials(self, request, pk=None):
        process = self.get_object()
        return Response({
            'inputs': [m.name for m in process.input_materials],
            'outputs': [m.name for m in process.output_materials]
        })
    
    @action(detail=True, methods=['get'])
    def parameters(self, request, pk=None):
        process = self.get_object()
        params = ProcessOperatingParameterSerializer(
            process.operating_parameters.all(), many=True
        )
        return Response(params.data)
```

**Files to create:**
- `processes/viewsets.py` (~200-300 lines)

**Pattern reference:** `case_studies/soilcom/viewsets.py`

---

### 4.3 Create Router (`router.py`)

```python
# processes/router.py

from rest_framework import routers
from .viewsets import ProcessViewSet, ProcessCategoryViewSet

router = routers.DefaultRouter()
router.register(r'processes', ProcessViewSet, basename='process')
router.register(r'categories', ProcessCategoryViewSet, basename='processcategory')
```

**Files to create:**
- `processes/router.py` (~20 lines)

---

## Phase 5: Testing

### 5.1 View Tests

**Priority: HIGH** - Essential for production

```python
# processes/tests/test_views.py

from utils.tests.testcases import AbstractTestCases

class ProcessCategoryCRUDViewsTestCase(
    AbstractTestCases.UserCreatedObjectCRUDViewTestCase
):
    modal_detail_view = True
    modal_update_view = True
    modal_create_view = True
    
    model = ProcessCategory
    
    view_dashboard_name = 'processes:dashboard'
    view_create_name = 'processes:processcategory-create'
    view_modal_create_name = 'processes:processcategory-create-modal'
    view_published_list_name = 'processes:processcategory-list'
    view_private_list_name = 'processes:processcategory-list-owned'
    view_detail_name = 'processes:processcategory-detail'
    view_modal_detail_name = 'processes:processcategory-detail-modal'
    view_update_name = 'processes:processcategory-update'
    view_modal_update_name = 'processes:processcategory-update-modal'
    view_delete_name = 'processes:processcategory-delete-modal'
    
    create_object_data = {'name': 'Test Category'}
    update_object_data = {'name': 'Updated Test Category'}

# Similar for Process with inlines
class ProcessCRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase):
    # ... with inline handling
    pass
```

**Files to create:**
- `processes/tests/test_views.py` (~400-600 lines)

**Pattern reference:** `materials/tests/test_views.py`

---

### 5.2 Form Tests

**Priority: MEDIUM**

```python
# processes/tests/test_forms.py

class ProcessCategoryFormTestCase(TestCase):
    def test_valid_form(self):
        form = ProcessCategoryModelForm(data={'name': 'Test'})
        self.assertTrue(form.is_valid())
    
    def test_invalid_empty_name(self):
        form = ProcessCategoryModelForm(data={'name': ''})
        self.assertFalse(form.is_valid())

class ProcessFormWithInlinesTestCase(TestCase):
    # Test inline formsets for materials, parameters
    pass
```

**Files to create:**
- `processes/tests/test_forms.py` (~200-300 lines)

**Pattern reference:** `case_studies/soilcom/tests/test_forms.py`

---

### 5.3 Filter Tests

```python
# processes/tests/test_filters.py

class ProcessFilterTestCase(TestCase):
    def test_filter_by_name(self):
        # Test filtering works correctly
        pass
```

**Files to create:**
- `processes/tests/test_filters.py` (~100-200 lines)

---

### 5.4 API Tests (if implementing API)

```python
# processes/tests/test_viewsets.py
# processes/tests/test_serializers.py
```

**Files to create:**
- `processes/tests/test_viewsets.py`
- `processes/tests/test_serializers.py`

---

## Phase 6: Additional Features

### 6.1 Signals (Optional)

**Priority: LOW** - For advanced automation

```python
# processes/signals.py

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import Process

@receiver(post_save, sender=Process)
def process_post_save(sender, instance, created, **kwargs):
    if created:
        # Log creation, send notifications, etc.
        pass
```

**Files to create:**
- `processes/signals.py` (~100 lines)

**Pattern reference:** `case_studies/soilcom/signals.py`

---

### 6.2 Tasks (Optional - for async operations)

**Priority: LOW** - Only if needed for heavy operations

```python
# processes/tasks.py

from celery import shared_task

@shared_task
def generate_process_report(process_id):
    # Generate PDF report or other heavy task
    pass
```

**Files to create:**
- `processes/tasks.py` (~100-200 lines)

**Pattern reference:** `case_studies/soilcom/tasks.py`

---

### 6.3 Utilities

**Priority: LOW**

```python
# processes/utils.py

def calculate_process_efficiency(process):
    # Helper functions for business logic
    pass
```

**Files to create:**
- `processes/utils.py` (~100-200 lines)

---

## Phase 7: Documentation & Deployment

### 7.1 Update Documentation

- Update README.md with usage instructions
- Document API endpoints (if implemented)
- Add migration guide for users
- Create admin user guide

### 7.2 Migrations

- Review all model changes
- Test migrations on staging
- Prepare rollback plan

---

## Implementation Priority Summary

### Must Have (Phase 1-3) - MVP
1. ✅ **Forms** - Required for all CRUD
2. ✅ **Views** - Core functionality
3. ✅ **URLs** - Routing
4. ✅ **Templates** - User interface
5. ✅ **View Tests** - Quality assurance
6. ⚠️ **Filters** - Nice to have but can be minimal

### Should Have (Phase 4)
7. **API (Serializers + ViewSets)** - For integrations
8. **Form Tests** - Better coverage
9. **Filter Tests** - Complete testing

### Could Have (Phase 5-6)
10. **Signals** - Advanced automation
11. **Tasks** - Async processing
12. **Utils** - Helper functions
13. **API Tests** - If API is implemented

---

## Estimated Effort

Based on soilcom complexity and materials simplicity:

| Phase | Component | Lines of Code | Effort (hours) |
|-------|-----------|---------------|----------------|
| 1 | Forms | ~500 | 8-12 |
| 1 | Filters | ~300 | 4-6 |
| 2 | Views | ~1000 | 16-24 |
| 2 | URLs | ~150 | 2-4 |
| 3 | Templates | ~15 files | 20-30 |
| 4 | Serializers | ~400 | 6-8 |
| 4 | ViewSets | ~300 | 4-6 |
| 5 | Tests (all) | ~1200 | 16-24 |
| **Total MVP** | | **~2350** | **40-60 hours** |
| **Total Full** | | **~4000** | **76-114 hours** |

---

## Quick Start Checklist

### Week 1: Foundation
- [ ] Create `forms.py` with all model forms
- [ ] Create basic `filters.py`
- [ ] Update `views.py` with ProcessCategory CRUD
- [ ] Create templates for ProcessCategory
- [ ] Update `urls.py` for ProcessCategory

### Week 2: Core Process CRUD
- [ ] Implement Process CRUD views with inlines
- [ ] Create Process templates with tabs
- [ ] Implement material/parameter management views
- [ ] Write view tests for ProcessCategory

### Week 3: Testing & Polish
- [ ] Write view tests for Process
- [ ] Write form tests
- [ ] Fix bugs and edge cases
- [ ] UI/UX improvements

### Week 4: API & Advanced Features
- [ ] Implement serializers
- [ ] Implement viewsets
- [ ] API tests
- [ ] Documentation

---

## Common Patterns to Follow

### 1. View Inheritance Pattern
```python
# Always inherit from utils.object_management.views
from utils.object_management.views import UserCreatedObjectCreateView
```

### 2. Form Pattern
```python
# Standard + Modal versions
ProcessCategoryModelForm  # Full form
ProcessCategoryModalModelForm  # Simplified for modals
```

### 3. URL Naming Pattern
```
{model_name_lower}-{action}
{model_name_lower}-{action}-modal
```

### 4. Template Naming Pattern
```
{model_name_lower}_list.html
{model_name_lower}_detail.html
{model_name_lower}_detail_modal.html
{model_name_lower}_form.html
```

### 5. Test Naming Pattern
```python
class {ModelName}CRUDViewsTestCase(AbstractTestCases.UserCreatedObjectCRUDViewTestCase)
```

---

## Migration Strategy

### Option A: Big Bang (Recommended for small teams)
- Implement all MVP features in development branch
- Test thoroughly
- Deploy all at once with feature flag

### Option B: Incremental (Recommended for production)
1. Keep mock views at current URLs
2. Add new CRUD at different URLs (e.g., `/processes/manage/`)
3. Add feature flag to toggle old/new interface
4. Migrate users gradually
5. Remove mock views when confident

---

## Success Criteria

- [ ] All models have full CRUD operations
- [ ] All views have corresponding tests (>80% coverage)
- [ ] All forms validated and working
- [ ] Templates responsive and accessible
- [ ] API endpoints documented (if implemented)
- [ ] No mock data in production
- [ ] User documentation complete
- [ ] Admin can manage all entities

---

## Next Immediate Steps

1. **Create `processes/forms.py`** - Start with ProcessCategoryModelForm
2. **Update `processes/views.py`** - Replace ProcessDashboard with real dashboard
3. **Create first CRUD set** - ProcessCategory as proof of concept
4. **Test thoroughly** - Use materials module tests as template
5. **Iterate** - Apply pattern to Process and related models

---

## References

### Code Examples
- **Full featured:** `/case_studies/soilcom/`
- **Mid complexity:** `/materials/`
- **Base classes:** `/utils/object_management/`
- **Testing patterns:** `/utils/tests/testcases.py`

### Documentation
- Django Class-Based Views: https://docs.djangoproject.com/en/stable/topics/class-based-views/
- DRF ViewSets: https://www.django-rest-framework.org/api-guide/viewsets/
- Crispy Forms: https://django-crispy-forms.readthedocs.io/

---

**This roadmap transforms processes from a demo module to a production-ready, fully-featured Django application following BRIT project conventions.**

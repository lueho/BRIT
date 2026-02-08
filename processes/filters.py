from django_filters import CharFilter, ModelChoiceFilter
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.filters import UserCreatedObjectScopedFilterSet
from utils.object_management.permissions import (
    apply_scope_filter,
    filter_queryset_for_user,
)

from .models import MechanismCategory, ProcessGroup, ProcessType


class ProcessGroupListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=ProcessGroup.objects.none(),
        field_name="name",
        label="Group Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="processgroup-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = ProcessGroup.objects.all()
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

    class Meta:
        model = ProcessGroup
        fields = ("scope", "name")


class MechanismCategoryListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=MechanismCategory.objects.none(),
        field_name="name",
        label="Mechanism Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="mechanismcategory-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = MechanismCategory.objects.all()
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

    class Meta:
        model = MechanismCategory
        fields = ("scope", "name")


class ProcessTypeListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=ProcessType.objects.none(),
        field_name="name",
        label="Process Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="processtype-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )
    group = ModelChoiceFilter(
        queryset=ProcessGroup.objects.all(),
        field_name="group",
        label="Group",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="processgroup-autocomplete",
            ),
        ),
    )
    mechanism = CharFilter(
        field_name="mechanism",
        lookup_expr="icontains",
        label="Mechanism",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = ProcessType.objects.all()
        if request and hasattr(request, "user"):
            queryset = filter_queryset_for_user(queryset, request.user)

        scope_value = None
        try:
            if hasattr(self, "data") and self.data:
                scope_value = self.data.get("scope")
            if not scope_value and hasattr(self, "form"):
                scope_value = self.form.initial.get("scope")
        except Exception:
            scope_value = None

        if scope_value:
            queryset = apply_scope_filter(
                queryset, scope_value, user=getattr(request, "user", None)
            )

        self.filters["name"].queryset = queryset

    class Meta:
        model = ProcessType
        fields = (
            "scope",
            "name",
            "group",
            "mechanism",
        )

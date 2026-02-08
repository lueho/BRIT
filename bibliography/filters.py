from django.db.models import Q
from django_filters import CharFilter, FilterSet, ModelChoiceFilter
from django_tomselect.app_settings import TomSelectConfig
from django_tomselect.widgets import TomSelectModelWidget

from utils.filters import UserCreatedObjectScopedFilterSet
from utils.object_management.permissions import (
    apply_scope_filter,
    filter_queryset_for_user,
)

from .models import Author, Licence, Source


class AuthorFilterSet(UserCreatedObjectScopedFilterSet):
    last_names = CharFilter(lookup_expr="icontains")
    first_names = CharFilter(lookup_expr="icontains")

    class Meta:
        model = Author
        fields = ("scope", "last_names", "first_names")


class LicenceListFilter(UserCreatedObjectScopedFilterSet):
    name = ModelChoiceFilter(
        queryset=Licence.objects.none(),
        field_name="name",
        label="Licence Name",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="licence-autocomplete",
                filter_by=("scope", "name"),
            ),
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(self, "request", None)
        queryset = Licence.objects.all()
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
        model = Licence
        fields = ("scope", "name")


def author_icontains(queryset, _, value):
    return queryset.filter(
        Q(authors__last_names__icontains=value)
        | Q(authors__first_names__icontains=value)
    ).distinct()


class SourceModelFilterSet(FilterSet):
    authors = CharFilter(method=author_icontains, label="Author names contain")
    title = CharFilter(lookup_expr="icontains")

    class Meta:
        model = Source
        fields = ("authors", "title", "type", "year")


class SourceFilter(UserCreatedObjectScopedFilterSet):
    title = ModelChoiceFilter(
        queryset=Source.objects.all(),
        label="Title",
        method="filter_by_source",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="source-autocomplete",
                label_field="text",
            ),
        ),
    )

    def filter_by_source(self, queryset, name, value):
        if value:
            return queryset.filter(pk=value.pk)
        return queryset

    author = ModelChoiceFilter(
        queryset=Author.objects.all(),
        field_name="authors",
        label="Author",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="author-autocomplete",
                label_field="label",
            ),
        ),
    )
    licence = ModelChoiceFilter(
        queryset=Licence.objects.all(),
        label="Licence",
        widget=TomSelectModelWidget(
            config=TomSelectConfig(
                url="licence-autocomplete",
            ),
        ),
    )

    class Meta:
        model = Source
        fields = ("scope", "title", "author", "type", "year", "licence")

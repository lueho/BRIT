from django.forms import Select
from django_filters import CharFilter

from utils.filters import UserCreatedObjectScopedFilterSet

from .models import Showcase

COUNTRY_CHOICES = (
    ("", "All countries"),
    ("BE", "Belgium"),
    ("DE", "Germany"),
    ("DK", "Denmark"),
    ("FR", "France"),
    ("NL", "The Netherlands"),
    ("NO", "Norway"),
    ("SE", "Sweden"),
)


class ShowcaseFilterSet(UserCreatedObjectScopedFilterSet):
    country = CharFilter(
        field_name="region__country",
        lookup_expr="exact",
        label="Country",
        widget=Select(choices=COUNTRY_CHOICES),
    )

    class Meta:
        model = Showcase
        fields = (
            "scope",
            "id",
            "country",
        )

from django.contrib.auth.models import AnonymousUser
from django.forms import Select
from django_filters import CharFilter, ChoiceFilter, ModelChoiceFilter

from maps.models import Catchment
from utils.filters import UserCreatedObjectScopedFilterSet
from utils.object_management.permissions import filter_queryset_for_user

from .models import Showcase
from .themes import THEME_CHOICES

COUNTRY_CHOICES = (
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
    theme = ChoiceFilter(choices=THEME_CHOICES, label="Theme")
    pilot_region = ModelChoiceFilter(
        field_name="catchment",
        queryset=Catchment.objects.none(),
        label="Pilot region / TBN",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = getattr(self.request, "user", None) or AnonymousUser()
        showcases = filter_queryset_for_user(self.queryset, user)
        pilots = Catchment.objects.filter(pk__in=showcases.values("catchment_id"))
        self.filters["pilot_region"].queryset = filter_queryset_for_user(pilots, user)

    class Meta:
        model = Showcase
        fields = ("scope", "id", "country", "theme", "pilot_region")


class ShowcaseAPIFilterSet(ShowcaseFilterSet):
    region__country = CharFilter(field_name="region__country", lookup_expr="exact")

    class Meta(ShowcaseFilterSet.Meta):
        fields = (*ShowcaseFilterSet.Meta.fields, "region__country")

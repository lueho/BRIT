from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from distributions.models import Period, TemporalDistribution, Timestep
from materials.models import MaterialCategory
from utils.object_management.models import get_default_owner

from .models import (
    BinConfiguration,
    CollectionCountOptions,
    CollectionFrequency,
    CollectionSeason,
)

INITIALIZATION_DEPENDENCIES = ["distributions", "materials"]


def ensure_initial_data(stdout=None):
    owner = get_default_owner()

    MaterialCategory.objects.get_or_create(
        owner=owner,
        name="Biowaste component",
        defaults={
            "publication_status": "published",
            "approved_at": timezone.now(),
            "approved_by": owner,
        },
    )

    try:
        distribution = TemporalDistribution.objects.get(
            owner=owner, name="Months of the year"
        )
        january = Timestep.objects.get(
            owner=owner, distribution=distribution, name="January"
        )
        december = Timestep.objects.get(
            owner=owner, distribution=distribution, name="December"
        )
        season = Period.objects.get(
            distribution=distribution, first_timestep=january, last_timestep=december
        )
    except ObjectDoesNotExist:
        raise RuntimeError(
            "Distributions initial data missing: ensure 'Months of the year', all time steps and the full-year period exist."
        ) from None

    frequency, _ = CollectionFrequency.objects.get_or_create(
        name="Fixed; 52 per year (1 per week)", type="Fixed"
    )
    CollectionCountOptions.objects.get_or_create(
        season=season, frequency=frequency, standard=52
    )

    CollectionSeason.objects.get_or_create(
        distribution=distribution, first_timestep=january, last_timestep=december
    )

    for method_name in (
        "Separate bins",
        "Optical bag sorting",
        "Four compartments bin",
        "Two compartments bin",
    ):
        BinConfiguration.objects.get_or_create(name=method_name)
    if stdout:
        print("Waste collection initial data ensured.", file=stdout)

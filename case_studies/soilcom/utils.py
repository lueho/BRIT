from django.core.exceptions import ObjectDoesNotExist

from distributions.models import Period, TemporalDistribution, Timestep
from utils.object_management.models import get_default_owner

from .models import CollectionCountOptions, CollectionFrequency, CollectionSeason

INITIALIZATION_DEPENDENCIES = ["distributions"]


def ensure_initial_data(stdout=None):

    owner = get_default_owner()

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
        )

    frequency, _ = CollectionFrequency.objects.get_or_create(
        name="Fixed; 52 per year (1 per week)", type="Fixed"
    )
    CollectionCountOptions.objects.get_or_create(
        season=season, frequency=frequency, standard=52
    )

    CollectionSeason.objects.get_or_create(
        distribution=distribution, first_timestep=january, last_timestep=december
    )

    if stdout:
        print("Soilcom initial data ensured.", file=stdout)

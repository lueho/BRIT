"""
Initial data setup for the soilcom submodule.
Implements autodiscovery-compatible ensure_initial_data().
"""
from django.conf import settings
from django.db import transaction
from users.utils import get_default_owner

def ensure_initial_data(stdout=None):
    """
    Ensures all required initial data for the soilcom submodule exists.
    Idempotent: safe to run multiple times.
    DEPENDENCY: Requires distributions initial data (distribution 'Months of the year', timesteps 'January'/'December', and period) to already exist.
    """
    from distributions.models import TemporalDistribution, Timestep, Period
    from .models import CollectionFrequency, CollectionCountOptions, CollectionSeason
    from django.core.exceptions import ObjectDoesNotExist
    owner = get_default_owner()

    # Defensive: check required distributions data exists
    try:
        distribution = TemporalDistribution.objects.get(owner=owner, name='Months of the year')
        january = Timestep.objects.get(owner=owner, distribution=distribution, name='January')
        december = Timestep.objects.get(owner=owner, distribution=distribution, name='December')
        season = Period.objects.get(distribution=distribution, first_timestep=january, last_timestep=december)
    except ObjectDoesNotExist:
        raise RuntimeError("Distributions initial data missing: ensure 'Months of the year', 'January', 'December', and the full-year period exist before running soilcom initial data.")

    # 1. CollectionFrequency: Fixed; 52 per year (1 per week)
    frequency, _ = CollectionFrequency.objects.get_or_create(name='Fixed; 52 per year (1 per week)', type='Fixed')
    # 2. CollectionCountOptions: season, frequency, standard=52
    CollectionCountOptions.objects.get_or_create(
        season=season,
        frequency=frequency,
        standard=52
    )

    # 4. CollectionSeason: whole year (if required by soilcom tests)
    CollectionSeason.objects.get_or_create(
        distribution=distribution,
        first_timestep=january,
        last_timestep=december
    )

    if stdout:
        print('Soilcom initial data ensured.', file=stdout)

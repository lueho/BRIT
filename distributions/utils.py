from django.utils import timezone

from utils.object_management.models import get_default_owner

INITIALIZATION_DEPENDENCIES = ["object_management"]


def ensure_initial_data(stdout=None):
    """
    Ensures all required initial data for the distributions app exists.
    Idempotent: safe to run multiple times.
    """
    from distributions.models import Period, TemporalDistribution, Timestep

    owner = get_default_owner()
    # Shared reference defaults every editor selects in frequency schedules,
    # so they must be readable references, not the default owner's private rows.
    published = {
        "publication_status": "published",
        "approved_at": timezone.now(),
        "approved_by": owner,
    }

    # 1. TemporalDistribution: Months of the year
    months_dist, _ = TemporalDistribution.objects.get_or_create(
        owner=owner, name="Months of the year", defaults=published
    )
    avg_dist, _ = TemporalDistribution.objects.get_or_create(
        owner=owner, name="Average", defaults=published
    )

    # 2. Timesteps for 'Months of the year'
    january, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="January", defaults=published
    )
    february, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="February", defaults=published
    )
    march, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="March", defaults=published
    )
    april, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="April", defaults=published
    )
    may, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="May", defaults=published
    )
    june, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="June", defaults=published
    )
    july, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="July", defaults=published
    )
    august, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="August", defaults=published
    )
    september, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="September", defaults=published
    )
    october, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="October", defaults=published
    )
    november, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="November", defaults=published
    )
    december, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="December", defaults=published
    )

    # 3. Period for 'Months of the year'
    period, _ = Period.objects.get_or_create(
        distribution=months_dist,
        first_timestep=january,
        last_timestep=december,
        defaults=published,
    )

    # 4. Timestep and Period for 'Average'
    avg_timestep, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=avg_dist, name="Average", defaults=published
    )
    avg_period, _ = Period.objects.get_or_create(
        distribution=avg_dist,
        first_timestep=avg_timestep,
        last_timestep=avg_timestep,
        defaults=published,
    )

    if stdout:
        print("Distributions initial data ensured.", file=stdout)

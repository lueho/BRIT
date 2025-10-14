from utils.object_management.models import get_default_owner

INITIALIZATION_DEPENDENCIES = ["users"]


def ensure_initial_data(stdout=None):
    """
    Ensures all required initial data for the distributions app exists.
    Idempotent: safe to run multiple times.
    """
    from distributions.models import Period, TemporalDistribution, Timestep

    owner = get_default_owner()

    # 1. TemporalDistribution: Months of the year
    months_dist, _ = TemporalDistribution.objects.get_or_create(
        owner=owner, name="Months of the year"
    )
    avg_dist, _ = TemporalDistribution.objects.get_or_create(
        owner=owner, name="Average"
    )

    # 2. Timesteps for 'Months of the year'
    january, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="January"
    )
    february, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="February"
    )
    march, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="March"
    )
    april, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="April"
    )
    may, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="May"
    )
    june, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="June"
    )
    july, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="July"
    )
    august, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="August"
    )
    september, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="September"
    )
    october, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="October"
    )
    november, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="November"
    )
    december, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=months_dist, name="December"
    )

    # 3. Period for 'Months of the year'
    period, _ = Period.objects.get_or_create(
        distribution=months_dist, first_timestep=january, last_timestep=december
    )

    # 4. Timestep and Period for 'Average'
    avg_timestep, _ = Timestep.objects.get_or_create(
        owner=owner, distribution=avg_dist, name="Average"
    )
    avg_period, _ = Period.objects.get_or_create(
        distribution=avg_dist, first_timestep=avg_timestep, last_timestep=avg_timestep
    )

    if stdout:
        print("Distributions initial data ensured.", file=stdout)

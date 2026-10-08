from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from utils.object_management.permissions import filter_queryset_for_user

from .models import Process


def with_process_count(queryset, publication_status=None, user=None):
    """Annotate categories with the number of linked processes.

    ``user`` restricts the counted processes to the caller's read policy so
    counts match what the list and detail views actually display.
    """
    process_category = Process.categories.through
    process_filter = {"processcategory_id": OuterRef("pk")}
    if publication_status is not None:
        process_filter["process__publication_status"] = publication_status
    if user is not None:
        process_filter["process__in"] = filter_queryset_for_user(
            Process.objects.all(), user
        ).values("pk")
    counts = (
        process_category.objects.filter(**process_filter)
        .values("processcategory_id")
        .annotate(count=Count("process_id", distinct=True))
        .values("count")
    )
    return queryset.annotate(
        process_count=Coalesce(
            Subquery(counts, output_field=IntegerField()),
            Value(0),
        )
    )


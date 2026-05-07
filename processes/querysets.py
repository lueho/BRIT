from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from .models import Process


def with_process_count(queryset, publication_status=None):
    process_category = Process.categories.through
    process_filter = {"processcategory_id": OuterRef("pk")}
    if publication_status is not None:
        process_filter["process__publication_status"] = publication_status
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


def with_published_process_count(queryset):
    return with_process_count(queryset, publication_status="published")

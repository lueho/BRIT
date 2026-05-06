from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from .models import Process


def with_published_process_count(queryset):
    process_category = Process.categories.through
    counts = (
        process_category.objects.filter(
            processcategory_id=OuterRef("pk"),
            process__publication_status="published",
        )
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

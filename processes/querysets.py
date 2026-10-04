from django.db.models import (
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Prefetch,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce

from bibliography.models import Author, Licence, Source, SourceAuthor
from utils.object_management.permissions import filter_queryset_for_user

from .models import Process, ProcessAuthor, ProcessCategory


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


def visible_prefetch(lookup, queryset, user):
    """Prefetch ``lookup`` restricted to rows ``user`` may read."""

    return Prefetch(lookup, queryset=filter_queryset_for_user(queryset, user))


def annotate_parent_is_visible(queryset, user):
    """Annotate each process with whether ``user`` may read its parent."""

    return queryset.annotate(
        parent_is_visible=Exists(
            filter_queryset_for_user(
                Process.objects.filter(pk=OuterRef("parent_id")), user
            )
        )
    )


def source_has_hidden_authors(user):
    """Exists-subquery flagging sources that link an author ``user`` may not read."""
    return Exists(
        SourceAuthor.objects.filter(source=OuterRef("pk")).exclude(
            author__in=filter_queryset_for_user(Author.objects.all(), user)
        )
    )


def visible_process_relations(queryset, user):
    """Prefetch nested relations through the read policy.

    ``ProcessListSerializer``/``ProcessDetailSerializer`` serialize nested
    categories, sources and the parent name. Without a filtered prefetch the
    related managers would expose objects the user may not read. The
    ``parent_is_visible`` annotation lets the serializer resolve the parent
    name without a per-object policy query.
    """

    return annotate_parent_is_visible(
        queryset.prefetch_related(
            visible_prefetch("categories", ProcessCategory.objects.all(), user),
            Prefetch(
                "sources",
                queryset=filter_queryset_for_user(Source.objects.all(), user)
                .select_related("licence")
                .prefetch_related(
                    Prefetch(
                        "sourceauthors",
                        queryset=SourceAuthor.objects.filter(
                            author__in=filter_queryset_for_user(
                                Author.objects.all(), user
                            )
                        )
                        .select_related("author")
                        .order_by("position"),
                    )
                )
                .annotate(
                    licence_is_visible=Exists(
                        filter_queryset_for_user(
                            Licence.objects.filter(pk=OuterRef("licence_id")),
                            user,
                        )
                    ),
                    has_hidden_authors=source_has_hidden_authors(user),
                ),
            ),
            Prefetch(
                "process_authors",
                queryset=ProcessAuthor.objects.filter(
                    author__in=filter_queryset_for_user(Author.objects.all(), user)
                )
                .select_related("author")
                .order_by("position", "author_id", "id"),
            ),
        ),
        user,
    )

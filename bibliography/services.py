"""Shared authorized helpers for bibliography creation workflows.

The quick-create endpoints, the REST API serializer, and the BibTeX import
delegate to ``create_source_with_authors`` so authorization, author
resolution, and atomicity are defined once by the shared object-management
policy. Standard HTML create/update views validate through their forms and
inlines instead.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from utils.object_management.policy import decide, visible_queryset
from utils.object_management.services import (
    _fresh_actor,
    authorize_create,
    record_creation,
    validate_references,
)

from .models import (
    AUTHOR_TYPES,
    LETTERLESS_ORGANIZATION_NAME_MESSAGE,
    LETTERLESS_SURNAME_MESSAGE,
    Author,
    Licence,
    Source,
    SourceAuthor,
    author_name_has_letter,
)

AUTHOR_ADD_DENIED_MESSAGE = "You need permission to create authors for source creation."
UNKNOWN_AUTHOR_MESSAGE = "The referenced author does not exist or is not accessible."
AUTHENTICATION_REQUIRED_MESSAGE = "An active account is required."

_SOURCE_WRITABLE_FIELDS = frozenset(
    {
        "citation_key",
        "title",
        "type",
        "licence",
        "publisher",
        "journal",
        "volume",
        "number",
        "eid",
        "pages",
        "month",
        "year",
        "abstract",
        "attributions",
        "url",
        "doi",
        "last_accessed",
    }
)

_AUTHOR_WRITABLE_FIELDS = (
    "author_type",
    "first_names",
    "middle_names",
    "last_names",
    "suffix",
    "preferred_citation",
    "institution",
    "organization_name",
    "organization_abbreviation",
    "contact_email",
)


def _normalize(value):
    return " ".join(str(value or "").split())


def _active_actor(actor):
    """Fresh actor with an active authenticated account, or denied."""
    actor = _fresh_actor(actor)
    if not getattr(actor, "is_active", False) or not getattr(
        actor, "is_authenticated", False
    ):
        raise PermissionDenied(AUTHENTICATION_REQUIRED_MESSAGE)
    return actor


def _visible_authors(actor):
    """Authors the actor may reference — invisible private rows are excluded."""
    return visible_queryset(actor, Author.objects.all())


def _author_field_map(author_data):
    return {
        field: _normalize(author_data.get(field))
        for field in _AUTHOR_WRITABLE_FIELDS
        if _normalize(author_data.get(field))
    }


def _create_author(actor, fields):
    """Authorize, persist, and audit a new Author inside one atomic block."""
    with transaction.atomic():
        actor = authorize_create(actor, Author)
        author = Author(owner=actor, **fields)
        author.full_clean()
        author.save()
        record_creation(actor, author)
    return author


def resolve_author_for_source(actor, author_data, *, allow_create):
    """Resolve one author payload entry to an accessible ``Author``.

    ``author_data`` is a mapping with either an ``id`` referencing an existing
    author or name fields describing a new/reusable author. Lookups run on the
    read-visible queryset so private records owned by others can neither be
    referenced nor discovered by name. ``allow_create`` only narrows access:
    a genuinely new author still goes through the authoritative
    ``authorize_create`` check and its ``created`` audit is recorded by this
    resolver itself, inside the caller's transaction.

    Raises ``ValidationError`` for invalid/inaccessible references and
    ``PermissionDenied`` when creation of a new author is not permitted.
    Returns ``(author, created)``.
    """
    actor = _active_actor(actor)
    if not isinstance(author_data, dict):
        raise ValidationError("Invalid author entry.")

    raw_id = author_data.get("id")
    if raw_id not in (None, ""):
        try:
            pk = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError(UNKNOWN_AUTHOR_MESSAGE) from exc
        author = _visible_authors(actor).filter(pk=pk).first()
        if author is None:
            raise ValidationError(UNKNOWN_AUTHOR_MESSAGE)
        return author, False

    author_type = author_data.get("author_type")
    if author_type in (None, ""):
        author_type = "person"
    elif author_type not in {value for value, _label in AUTHOR_TYPES}:
        raise ValidationError("Unsupported author type.")
    fields = _author_field_map(author_data)

    if author_type == "organization":
        organization_name = fields.get("organization_name", "")
        if not organization_name:
            raise ValidationError("Organizations need a name.")
        if not author_name_has_letter(organization_name):
            raise ValidationError(LETTERLESS_ORGANIZATION_NAME_MESSAGE)
        author = (
            _visible_authors(actor)
            .filter(
                author_type="organization",
                organization_name__iexact=organization_name,
            )
            .first()
        )
        if author is None:
            if not allow_create:
                raise PermissionDenied(AUTHOR_ADD_DENIED_MESSAGE)
            author = _create_author(
                actor,
                {
                    "author_type": "organization",
                    **{k: v for k, v in fields.items() if k != "author_type"},
                },
            )
            return author, True
        return author, False

    first_names = fields.get("first_names", "")
    last_names = fields.get("last_names", "")
    if not last_names:
        raise ValidationError("A non-empty last name is required to create an author.")
    if not author_name_has_letter(last_names):
        raise ValidationError(LETTERLESS_SURNAME_MESSAGE)

    candidates = _visible_authors(actor).filter(
        author_type="person",
        first_names__iexact=first_names,
        last_names__iexact=last_names,
    )
    suffix = fields.get("suffix", "")
    if suffix:
        candidates = candidates.filter(suffix__iexact=suffix)
    author = candidates.first()
    if author is None:
        if not allow_create:
            raise PermissionDenied(AUTHOR_ADD_DENIED_MESSAGE)
        author = _create_author(
            actor,
            {
                "author_type": "person",
                "first_names": first_names,
                "last_names": last_names,
                **{
                    k: v
                    for k, v in fields.items()
                    if k not in ("author_type", "first_names", "last_names")
                },
            },
        )
        return author, True
    return author, False


def create_source_with_authors(actor, source_data: dict, authors_data: list) -> Source:
    """Create a private ``Source`` with ordered author relations for ``actor``.

    - ``actor`` must hold the ``create`` capability on ``Source``.
    - Referenced authors must be visible to ``actor``; invisible or missing
      references fail with a uniform validation error.
    - Genuinely new authors require the ``create`` capability on ``Author``.
    - ``SourceAuthor`` rows are owned children of the source and need no
      separate permission.
    - Duplicate author references are deduplicated, first position wins.
    - Owner/lifecycle fields in ``source_data`` are ignored; the source is
      always created private with ``owner=actor``.
    - The whole write is atomic: any invalid entry rolls back all rows.
    """
    if not isinstance(authors_data, (list, tuple)) and authors_data is not None:
        raise ValidationError("authors_data must be a list of author entries.")
    if source_data is not None and not isinstance(source_data, dict):
        raise ValidationError("source_data must be a mapping of source fields.")

    cleaned = {
        key: value
        for key, value in (source_data or {}).items()
        if key in _SOURCE_WRITABLE_FIELDS
    }
    if not _normalize(cleaned.get("title")):
        raise ValidationError("A non-empty title is required to create a source.")
    cleaned["title"] = _normalize(cleaned.get("title"))

    with transaction.atomic():
        actor = authorize_create(actor, Source)

        licence = cleaned.get("licence")
        if licence == "":
            licence = None
            cleaned["licence"] = None
        if licence is not None:
            licence_pk = getattr(licence, "pk", licence)
            try:
                licence_pk = int(licence_pk)
            except (TypeError, ValueError):
                raise ValidationError(
                    "The referenced licence does not exist or is not accessible."
                ) from None
            licence = (
                visible_queryset(actor, Licence.objects.all())
                .filter(pk=licence_pk)
                .first()
            )
            if licence is None:
                raise ValidationError(
                    "The referenced licence does not exist or is not accessible."
                )
            cleaned["licence"] = licence

        can_create_author = decide(actor, "create", Author).allowed
        authors = []
        seen_ids = set()
        for author_data in authors_data or []:
            author, created = resolve_author_for_source(
                actor, author_data, allow_create=can_create_author
            )
            if author.pk not in seen_ids:
                seen_ids.add(author.pk)
                authors.append(author)

        source = Source(owner=actor, **cleaned)
        source.full_clean()
        # Re-read the actor immediately before reference validation and
        # persistence: a capability revoked while authors were resolved must
        # deny every later reference, not just the final create decision.
        actor = authorize_create(actor, Source)
        source.owner = actor
        validate_references(
            actor, {"licence": source.licence, "authors": list(authors)}
        )
        source.save()
        for position, author in enumerate(authors, start=1):
            SourceAuthor.objects.create(source=source, author=author, position=position)
        record_creation(actor, source)
    return source


def source_is_referenced(source) -> bool:
    """True when objects other than the source's own authors link to it."""
    for relation in source._meta.related_objects:
        if relation.related_model is SourceAuthor:
            continue
        field = getattr(relation, "field", None)
        if field is None:
            continue
        if relation.related_model._default_manager.filter(
            **{field.name: source}
        ).exists():
            return True
    return False

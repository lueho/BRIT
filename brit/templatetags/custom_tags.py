from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.simple_tag
def user_in_group(user, group_name):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return user.groups.filter(name=group_name).exists()


@register.filter
def verbose_name(obj):
    return obj._meta.verbose_name


@register.filter
def class_name(obj):
    return obj.__class__.__name__.lower()


@register.filter
def modulo(value, divisor):
    """Return ``value % divisor`` as an integer, or ``0`` on failure."""

    try:
        return int(value) % int(divisor)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0


@register.filter
def get_item(container, key):
    """Generic dict/mapping item access safe for template use."""

    if container is None:
        return None
    try:
        return container[key]
    except (KeyError, IndexError, TypeError):
        return getattr(container, str(key), None)


@register.filter
def trim_decimal(value, places=10):
    """Format numeric values without trailing zeros."""

    if value is None:
        return ""
    try:
        places_value = int(places) if places is not None else 10
    except (TypeError, ValueError):
        places_value = 10
    if places_value < 0:
        places_value = 0
    try:
        dec_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value

    if places_value == 0:
        quantizer = Decimal("1")
    else:
        quantizer = Decimal("1." + "0" * places_value)
    quantized = dec_value.quantize(quantizer)
    text = format(quantized, "f").rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _chip_format_range_bound(value):
    """Format date/datetime/numeric range bounds without noisy components."""
    if value is None:
        return ""
    if hasattr(value, "date"):
        return value.date().isoformat()
    if isinstance(value, (int, float, Decimal)):
        return trim_decimal(value)
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _chip_format_range(filter_, start, stop):
    """Render a range for chip display, appending the filter's unit if any."""
    unit = getattr(filter_, "unit", "") or ""
    start_txt = _chip_format_range_bound(start)
    stop_txt = _chip_format_range_bound(stop)
    if start_txt and stop_txt:
        return f"{start_txt} – {stop_txt} {unit}".rstrip()
    if start_txt:
        return f"from {start_txt} {unit}".rstrip()
    if stop_txt:
        return f"until {stop_txt} {unit}".rstrip()
    return ""


def _nullable_range_is_unconstrained(filter_, range_slice, include_nulls):
    """Return True when a nullable-range slider covers its full span plus nulls.

    Such a value matches every row, so advertising it as an active filter chip
    would be noise rather than information.
    """
    if not include_nulls:
        return False
    widget = getattr(getattr(filter_, "field", None), "widget", None)
    range_min = getattr(widget, "range_min", None)
    range_max = getattr(widget, "range_max", None)
    if range_min is None:
        getter = getattr(filter_, "get_filter_range_min", None)
        range_min = getter() if getter else None
    if range_max is None:
        getter = getattr(filter_, "get_filter_range_max", None)
        range_max = getter() if getter else None
    if range_min is None or range_max is None:
        return False
    covers_min = range_slice.start is None or float(range_slice.start) <= float(
        range_min
    )
    covers_max = range_slice.stop is None or float(range_slice.stop) >= float(range_max)
    return covers_min and covers_max


def _chip_display_value(filter_, value):
    """Render a human-readable label for an active filter value."""
    if isinstance(value, slice):
        return _chip_format_range(filter_, value.start, value.stop)
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], slice):
        # NullableRangeField compresses to (slice, include_nulls).
        range_slice, include_nulls = value
        if _nullable_range_is_unconstrained(filter_, range_slice, include_nulls):
            return ""
        display = _chip_format_range(filter_, range_slice.start, range_slice.stop)
        if include_nulls and display:
            display += " (incl. unknown)"
        return display
    if hasattr(value, "pk"):
        return str(value)
    field = getattr(filter_, "field", None)
    choices = getattr(field, "choices", None)
    if choices:
        try:
            label = dict(choices).get(value)
        except TypeError:
            label = None
        if label is not None:
            return str(label)
    if isinstance(value, (list, tuple)) or hasattr(value, "all"):
        return ", ".join(str(item) for item in value)
    return str(value)


@register.simple_tag(takes_context=True)
def active_filter_chips(context):
    """
    Return removable chips for the currently active django-filter filters.

    Reads the FilterSet from ``context["filter"]`` and the current request and
    returns a list of dicts with ``name``, ``label``, ``value`` and
    ``remove_url`` keys. Structural parameters (scope, pagination, ordering)
    are not treated as filters and never produce chips.
    """
    request = context.get("request")
    filterset = context.get("filter")
    if request is None or not hasattr(filterset, "filters"):
        return []

    skip = {"scope", "page", "id", "ordering", "publication_status"}
    filter_names = set(filterset.filters)
    if not any(
        key not in skip
        and (
            key in filter_names
            or any(key.startswith(f"{name}_") for name in filter_names)
        )
        for key in request.GET
    ):
        return []

    form = getattr(filterset, "form", None)
    if form is None or not form.is_valid():
        return []

    chips = []
    for name, filter_ in filterset.filters.items():
        if name in skip:
            continue
        value = form.cleaned_data.get(name)
        if value in (None, "", [], (), {}):
            continue
        display = _chip_display_value(filter_, value)
        if not display:
            continue
        params = request.GET.copy()
        for key in list(params.keys()):
            if key == name or (key.startswith(f"{name}_") and key not in filter_names):
                del params[key]
        params.pop("page", None)
        query = params.urlencode()
        chips.append(
            {
                "name": name,
                "label": filter_.label or name.replace("_", " ").title(),
                "value": display,
                "remove_url": (f"{request.path}?{query}" if query else request.path),
            }
        )
    return chips


# Solution from: https://www.caktusgroup.com/blog/2018/10/18/filtering-and-pagination-django/
@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Return encoded URL parameters that are the same as the current
    request's parameters, only with the specified GET parameters added or changed.

    It also removes any empty parameters to keep things neat,
    so you can remove a param by setting it to ``""``.

    For example, if you're on the page ``/things/?with_frosting=true&page=5``,
    then

    <a href="/things/?{% param_replace page=3 %}">Page 3</a>

    would expand to

    <a href="/things/?with_frosting=true&page=3">Page 3</a>

    Based on
    https://stackoverflow.com/questions/22734695/next-and-before-links-for-a-django-paginated-query/22735278#22735278
    """
    d = context["request"].GET.copy()
    for k, v in kwargs.items():
        d[k] = v
    for k in [k for k, v in d.items() if not v]:
        del d[k]
    return d.urlencode()


# Query parameters that control list presentation rather than constrain the
# result set: scope switching, pagination, ordering, and fields that leak into
# GET URLs (e.g. csrfmiddlewaretoken, see issue #153).
NON_FILTER_QUERY_PARAMS = frozenset(
    {
        "scope",
        "page",
        "id",
        "list_type",
        "ordering",
        "sort",
        "next",
        "csrfmiddlewaretoken",
    }
)


@register.simple_tag(takes_context=True)
def has_active_filters(context):
    """Return True when the request carries at least one constraining filter value."""
    request = context.get("request")
    if request is None:
        return False
    return any(
        value
        for key, value in request.GET.items()
        if key not in NON_FILTER_QUERY_PARAMS
    )

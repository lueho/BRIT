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


def _chip_format_temporal(value):
    """Format date/datetime range bounds without noisy time components."""
    if value is None:
        return ""
    if hasattr(value, "date"):
        return value.date().isoformat()
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _chip_display_value(filter_, value):
    """Render a human-readable label for an active filter value."""
    if isinstance(value, slice):
        start = _chip_format_temporal(value.start)
        stop = _chip_format_temporal(value.stop)
        if start and stop:
            return f"{start} – {stop}"
        if start:
            return f"from {start}"
        if stop:
            return f"until {stop}"
        return ""
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

    form = getattr(filterset, "form", None)
    if form is None or not form.is_valid():
        return []

    skip = {"scope", "page", "id", "ordering", "publication_status"}
    filter_names = set(filterset.filters)
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

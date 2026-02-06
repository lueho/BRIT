from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def verbose_name(obj):
    return obj._meta.verbose_name


@register.filter
def class_name(obj):
    return obj.__class__.__name__.lower()


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

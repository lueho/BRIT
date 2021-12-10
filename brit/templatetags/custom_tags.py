from django import template

register = template.Library()


@register.filter
def verbose_name(obj):
    return obj._meta.verbose_name


@register.filter
def class_name(obj):
    return obj.__class__.__name__.lower()

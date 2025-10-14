from django import template

register = template.Library()


@register.filter
def is_user_created(model_class):
    return getattr(model_class, 'user_created', False)

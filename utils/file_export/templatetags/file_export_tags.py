from urllib.parse import urlencode

from django import template
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

register = template.Library()


@register.inclusion_tag("../templates/export_link.html")
def export_link(file_format, export_url_name, progress_url_name=None):
    if file_format not in ["csv", "xlsx"]:
        raise ValueError('file_format must be "csv" or "xlsx"')
    if file_format == "csv":
        icon_class = "fa fa-fw fa-file-csv"
    elif file_format == "xlsx":
        icon_class = "fa fa-fw fa-file-excel"
    else:
        icon_class = "fa fa-fw fa-file"
    if not progress_url_name:
        progress_url_name = "file-export-progress"
    progress_url = reverse(progress_url_name, kwargs={"task_id": 0})
    text = f"Export to {file_format}"
    return {
        "id": f"export_{file_format}",
        "file_format": file_format,
        "export_url": reverse(export_url_name),
        "progress_url": progress_url,
        "icon_class": icon_class,
        "text": text,
    }


@register.simple_tag
def export_link_modal(export_url_name, **extra_params):
    """
    Return a link that opens the export modal using the existing modal framework.
    """
    export_url = reverse(export_url_name)
    modal_url = reverse("export-modal")
    params = {"export_url": export_url}
    params.update(extra_params)
    return f"{modal_url}?{urlencode(params)}"


@register.inclusion_tag("../templates/export_modal_button.html", takes_context=True)
def export_modal_button(
    context,
    export_url_name,
    *,
    button_classes="btn btn-outline-secondary w-100",
    text=None,
    icon_class="fas fa-file-export",
    hint_text=None,
    hint_classes="text-muted small mt-2 mb-0",
    element_id=None,
    **extra_params,
):
    """Render an export button that stays visible for anonymous users but disabled."""

    request = context.get("request")
    user = getattr(request, "user", None)
    is_authenticated = bool(user and getattr(user, "is_authenticated", False))

    export_url = reverse(export_url_name)
    modal_url = reverse("export-modal")

    params = {"export_url": export_url}
    for key, value in extra_params.items():
        if value is None:
            continue
        params[key] = value

    modal_href = f"{modal_url}?{urlencode(params, doseq=True)}"

    button_id = (
        element_id
        or f"export-modal-{export_url_name.replace(':', '-').replace('_', '-')}"
    )

    button_text = text if text is not None else _("Export data")
    login_hint = hint_text if hint_text is not None else _("Log in to enable export.")

    export_disabled = not is_authenticated

    return {
        "button_id": button_id,
        "button_classes": button_classes,
        "button_text": button_text,
        "icon_class": icon_class,
        "modal_href": modal_href,
        "export_disabled": export_disabled,
        "hint_text": login_hint,
        "hint_classes": hint_classes,
    }

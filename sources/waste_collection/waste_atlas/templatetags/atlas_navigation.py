"""Template tags rendering the Waste Atlas navigation fragments.

The selector option list and the shell-side map tree are large, static
structures that were previously emitted by nested template loops inside
``{% cache %}`` blocks.  Generating the same markup in Python keeps the
fragments identical while skipping the template engine's per-node work.
All dynamic values are passed through ``format_html``/``format_html_join``
so escaping matches the templates' autoescape behaviour exactly.
"""

from django import template
from django.urls import reverse
from django.utils.html import format_html, format_html_join

register = template.Library()


def _theme_option(map_set, option, selected_map_set, selected_theme):
    """Render one ``<option>`` matching the selector templates' markup."""
    value = option.get("value", "")
    theme_group = option.get("theme_group", "")
    label = option.get("label", "")
    search = f"{label.lower()} {value.lower()} {theme_group.lower()}"
    change_url = (
        format_html(' data-change-url="{}"', option["change_url"])
        if option.get("change_url")
        else ""
    )
    selected = (
        " selected" if map_set == selected_map_set and value == selected_theme else ""
    )
    return format_html(
        '<option value="{}" data-map-set="{}" data-theme-group="{}" '
        'data-waste-category="{}" data-search="{}" data-url="{}"{}{}>'
        "{}</option>",
        value,
        map_set,
        theme_group,
        option.get("waste_category", ""),
        search,
        option.get("url", ""),
        change_url,
        selected,
        label,
    )


@register.simple_tag
def atlas_theme_options(themes_by_map_set, selected_map_set, selected_theme):
    """Emit every theme ``<option>`` for the map/change map selectors."""
    return format_html_join(
        "",
        "{}",
        (
            (_theme_option(map_set, option, selected_map_set, selected_theme),)
            for map_set, themes in themes_by_map_set.items()
            for option in themes
        ),
    )


def _europe_map_link(map_):
    title = map_.get("title", "")
    return format_html(
        '<a class="atlas-tree-link" href="{}" data-search="{}">{}</a>',
        map_.get("url", ""),
        title.lower(),
        title,
    )


def _section_map_link(map_, region, active_map_set, active_theme):
    title = map_.get("title", "")
    theme = map_.get("theme", "")
    region_label = region.get("label", "")
    search = f"{title.lower()} {region_label.lower()} {theme.lower()}"
    is_active = region.get("value") == active_map_set and theme == active_theme
    if is_active:
        return format_html(
            '<a class="atlas-tree-link atlas-tree-link--active" '
            'aria-current="page" href="{}" data-search="{}">{}</a>',
            map_.get("url", ""),
            search,
            title,
        )
    return format_html(
        '<a class="atlas-tree-link" href="{}" data-search="{}">{}</a>',
        map_.get("url", ""),
        search,
        title,
    )


def _region_block(region, active_map_set, active_theme):
    sections = format_html_join(
        "",
        "{}",
        (
            (
                format_html(
                    '<div class="atlas-tree-section">'
                    '<div class="atlas-tree-section-title">{}</div>{}</div>',
                    section.get("label", ""),
                    format_html_join(
                        "",
                        "{}",
                        (
                            (
                                _section_map_link(
                                    map_, region, active_map_set, active_theme
                                ),
                            )
                            for map_ in section.get("maps") or []
                        ),
                    ),
                ),
            )
            for section in region.get("sections") or []
        ),
    )
    return format_html(
        '<div class="atlas-tree-region-block" data-map-set="{}">'
        '<div class="atlas-tree-region-title">{}</div>{}</div>',
        region.get("value", ""),
        region.get("label", ""),
        sections,
    )


def _region_group(
    group, overview_active, selected_region, active_map_set, active_theme
):
    children = []
    europe_maps = group.get("europe_maps") or []
    if europe_maps:
        children.append(
            format_html(
                '<div class="atlas-tree-section">{}</div>',
                format_html_join(
                    "",
                    "{}",
                    ((_europe_map_link(map_),) for map_ in europe_maps),
                ),
            )
        )
    children.extend(
        _region_block(region, active_map_set, active_theme)
        for region in group.get("regions") or []
    )
    opened = (
        " open" if (not overview_active and group.get("id") == selected_region) else ""
    )
    return format_html(
        '<details class="atlas-tree-region" data-region="{}"{}>'
        '<summary class="atlas-tree-region-summary">{}</summary>{}</details>',
        group.get("id", ""),
        opened,
        group.get("label", ""),
        format_html_join("", "{}", ((child,) for child in children)),
    )


@register.simple_tag(takes_context=True)
def atlas_shell_tree(context):
    """Emit the cached inner markup of ``includes/shell_tree.html``."""
    overview_active = context.get("atlas_tree_overview_active")
    selected_region = context.get("directory_selected_region")
    active_map_set = context.get("atlas_map_set")
    active_theme = context.get("atlas_active_theme")
    parts = [
        format_html(
            '<a class="atlas-tree-overview-link{}" href="{}">'
            '<i class="fas fa-th-list"></i> All maps</a>',
            (" atlas-tree-link--active" if overview_active else ""),
            reverse("waste-atlas-overview"),
        )
    ]
    parts.extend(
        _region_group(
            group,
            overview_active,
            selected_region,
            active_map_set,
            active_theme,
        )
        for group in context.get("directory_region_groups") or []
    )
    return format_html_join("", "{}", ((part,) for part in parts))

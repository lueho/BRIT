from copy import deepcopy

from django import forms

from .legend import (
    AUTO,
    EXPORT_LEGEND_ITEM_FLOW_CHOICES,
    EXPORT_LEGEND_OVERRIDE_KEYS,
    LEGACY_EXPORT_LEGEND_KEYS,
    normalize_columns,
    normalize_item_flow,
    normalize_placement,
    normalize_width_fraction,
    order_legend_values,
    quartile_legend_entries,
)
from .models import (
    LEGEND_PLACEMENTS,
    WasteAtlasRenderingSettings,
)

LEGEND_PLACEMENT_CHOICES = LEGEND_PLACEMENTS
EXPORT_LEGEND_PLACEMENT_CHOICES = (
    (AUTO, "Automatic"),
    ("right", "Right of map"),
    ("left", "Left of map"),
    ("bottom", "Below map"),
    ("bottom-right", "Page corner: bottom right"),
    ("bottom-left", "Page corner: bottom left"),
    ("top-right", "Page corner: top right"),
    ("top-left", "Page corner: top left"),
)
EXPORT_LEGEND_COLUMN_CHOICES = (
    (AUTO, "Automatic"),
    ("1", "1"),
    ("2", "2"),
    ("3", "3"),
    ("4", "4"),
)
# A blank arrangement inherits the atlas default, the same way a blank maximum
# width does; there is no "automatic" arrangement to decide.
EXPORT_LEGEND_ITEM_FLOW_FORM_CHOICES = (
    ("", "Atlas default"),
    *EXPORT_LEGEND_ITEM_FLOW_CHOICES,
)


class WasteAtlasMapConfigurationForm(forms.Form):
    """Edit the human-facing legend text without exposing raw JSON."""

    legend_title = forms.CharField(
        label="Legend title",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    legend_note = forms.CharField(
        label="Legend note (optional)",
        required=False,
        help_text="Shown below the legend on the map and in downloaded exports.",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    export_legend_title = forms.CharField(
        label="Export legend title (optional)",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )
    legend_placement = forms.ChoiceField(
        label="Placement",
        choices=LEGEND_PLACEMENT_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    legend_width = forms.IntegerField(
        label="Width (px)",
        min_value=180,
        max_value=600,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": 10}),
    )
    legend_font_size = forms.IntegerField(
        label="Text size (px)",
        min_value=8,
        max_value=24,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    show_only_present_categories = forms.BooleanField(
        label="Hide categories not present on this map",
        required=False,
        help_text=(
            "Applies to both the interactive map and downloaded exports. "
            "The categories remain configured and reappear whenever the "
            "selected region and year contain matching data."
        ),
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    export_legend_customize = forms.BooleanField(
        label="Customize the export legend for this map",
        required=False,
        help_text=(
            "When off, every export of this map uses the atlas defaults. "
            "Turn it on to set placement, columns, arrangement and maximum "
            "width."
        ),
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
                "data-atlas-toggle": "export-legend-custom",
            }
        ),
    )
    export_legend_placement = forms.ChoiceField(
        label="Placement",
        choices=EXPORT_LEGEND_PLACEMENT_CHOICES,
        required=False,
        help_text="Automatic lets the layout engine choose the best position.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    export_legend_columns = forms.ChoiceField(
        label="Columns",
        choices=EXPORT_LEGEND_COLUMN_CHOICES,
        required=False,
        help_text="Automatic chooses a suitable count; or pin an exact number.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    export_legend_item_flow = forms.ChoiceField(
        label="Arrangement",
        choices=EXPORT_LEGEND_ITEM_FLOW_FORM_CHOICES,
        required=False,
        help_text=(
            "Whether entries fill one column after another or read across the "
            "columns row by row. Applies to the export and to the map page. "
            "Blank keeps the atlas default."
        ),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    export_legend_width = forms.IntegerField(
        label="Maximum width (% of page)",
        min_value=20,
        max_value=90,
        required=False,
        help_text=(
            "Hard upper bound. The legend is fitted to its content and may be narrower."
        ),
        widget=forms.NumberInput(attrs={"class": "form-control", "step": 1}),
    )

    def __init__(self, *args, instance, **kwargs):
        self.instance = instance
        self._defaults = WasteAtlasRenderingSettings.load()
        self._configuration = deepcopy(instance.configuration)
        self._categories = self._configuration.get("categories", [])
        self._quartile_entries = quartile_legend_entries(self._configuration)

        initial = kwargs.setdefault("initial", {})
        initial.setdefault("legend_title", self._configuration.get("legendTitle", ""))
        initial.setdefault("legend_note", self._configuration.get("legendNote", ""))
        initial.setdefault(
            "export_legend_title",
            self._configuration.get("exportLegendTitle", ""),
        )
        initial.setdefault(
            "legend_placement",
            self._configuration.get("legendPlacement", self._defaults.legend_placement),
        )
        initial.setdefault(
            "legend_width",
            self._configuration.get("legendWidth", self._defaults.legend_width),
        )
        initial.setdefault(
            "legend_font_size",
            self._configuration.get("legendFontSize", self._defaults.legend_font_size),
        )
        initial.setdefault(
            "show_only_present_categories",
            self._configuration.get("showOnlyPresentCategories", False),
        )
        has_custom_export_legend = any(
            key in self._configuration for key in EXPORT_LEGEND_OVERRIDE_KEYS
        )
        initial.setdefault("export_legend_customize", has_custom_export_legend)
        initial.setdefault(
            "export_legend_placement",
            normalize_placement(self._configuration.get("exportLegendPlacement"))
            or AUTO,
        )
        stored_columns = normalize_columns(
            self._configuration.get("exportLegendColumns")
        )
        initial.setdefault(
            "export_legend_columns",
            AUTO if stored_columns in (None, AUTO) else str(stored_columns),
        )
        # Blank unless an override is stored, so inheritance stays durable: a
        # map customized for placement, columns or width keeps tracking the
        # atlas-wide arrangement instead of freezing today's value.
        initial.setdefault(
            "export_legend_item_flow",
            normalize_item_flow(self._configuration.get("exportLegendItemFlow")) or "",
        )
        stored_width = normalize_width_fraction(
            self._configuration.get("exportLegendWidth")
        )
        # Only pre-fill the width when an override is actually stored. Leaving
        # the field blank when it inherits keeps inheritance durable: a blank
        # reopen saves blank, so the map keeps tracking the atlas default rather
        # than freezing the resolved value on the next save.
        if stored_width is not None:
            initial.setdefault("export_legend_width", round(stored_width * 100))
        super().__init__(*args, **kwargs)

        # Surface the inherited atlas default as a placeholder (not a value) so a
        # blank field still communicates the effective maximum width.
        self.fields["export_legend_width"].widget.attrs.setdefault(
            "placeholder", round(self._defaults.export_legend_width_fraction * 100)
        )

        for index, category in enumerate(self._categories):
            self.fields[f"category_{index}_label"] = forms.CharField(
                label="Preview name",
                initial=category.get("label", ""),
                widget=forms.TextInput(attrs={"class": "form-control"}),
            )
            self.fields[f"category_{index}_export_label"] = forms.CharField(
                label="Export name (optional)",
                initial=category.get("exportLabel", ""),
                required=False,
                widget=forms.TextInput(attrs={"class": "form-control"}),
            )
        entry_order = self._entry_order()
        for prefix, _value in self._entries():
            self.fields[f"{prefix}_order"] = forms.IntegerField(
                label="Order",
                initial=entry_order.index(prefix) + 1,
                min_value=1,
                max_value=len(entry_order),
                widget=forms.NumberInput(attrs={"class": "form-control", "step": 1}),
            )

    def _entries(self):
        """Return ``(field prefix, legend value)`` for every orderable entry.

        The entries are the stored categories plus, for a quartile map, the
        classes the renderer derives from the data.  Quartile classification is
        a runtime toggle, so both sets share one saved order: each side of the
        toggle reads the positions of the entries it shows.
        """
        return [
            (f"category_{index}", category.get("value", ""))
            for index, category in enumerate(self._categories)
        ] + [
            (f"quartile_{entry['value']}", entry["value"])
            for entry in self._quartile_entries
        ]

    def _entry_order(self):
        """Return the field prefixes in the order the renderer would show them."""
        default_order = [
            f"category_{index}" for index in range(len(self._categories))
        ] + [f"quartile_{entry['value']}" for entry in self._quartile_entries]

        values = dict(self._entries())
        ordered_values = order_legend_values(
            [values[prefix] for prefix in default_order],
            self._configuration.get("legendCategoryOrder"),
        )
        return sorted(
            default_order,
            key=lambda prefix: ordered_values.index(values[prefix]),
        )

    @property
    def category_rows(self):
        quartile_labels = {
            f"quartile_{entry['value']}": entry for entry in self._quartile_entries
        }
        rows = []
        for position, (prefix, value) in enumerate(self._entries()):
            quartile = quartile_labels.get(prefix)
            category = None if quartile else self._categories[position]
            rows.append(
                (
                    self[f"{prefix}_order"].value(),
                    position,
                    {
                        "value": value,
                        "color": (quartile or category).get("color", ""),
                        "label": (quartile or category).get("label", ""),
                        "label_field": (None if quartile else self[f"{prefix}_label"]),
                        "export_label_field": (
                            None if quartile else self[f"{prefix}_export_label"]
                        ),
                        "order_field": self[f"{prefix}_order"],
                    },
                )
            )

        def position(entry):
            try:
                return int(entry[0])
            except (TypeError, ValueError):
                return len(rows) + entry[1]

        return [
            row
            for _, _, row in sorted(
                rows,
                key=position,
            )
        ]

    def clean(self):
        cleaned_data = super().clean()
        entries = self._entries()
        positions = [cleaned_data.get(f"{prefix}_order") for prefix, _value in entries]
        valid_positions = [position for position in positions if position is not None]
        if len(valid_positions) == len(entries) and len(set(valid_positions)) != len(
            valid_positions
        ):
            raise forms.ValidationError("Each category position must be unique.")
        return cleaned_data

    def save(self):
        configuration = deepcopy(self._configuration)
        configuration["legendTitle"] = self.cleaned_data["legend_title"]
        legend_note = self.cleaned_data["legend_note"]
        if legend_note:
            configuration["legendNote"] = legend_note
        else:
            configuration.pop("legendNote", None)
        configuration["legendPlacement"] = self.cleaned_data["legend_placement"]
        configuration["legendWidth"] = self.cleaned_data["legend_width"]
        configuration["legendFontSize"] = self.cleaned_data["legend_font_size"]
        if self.cleaned_data.get("show_only_present_categories"):
            configuration["showOnlyPresentCategories"] = True
        else:
            configuration.pop("showOnlyPresentCategories", None)

        export_title = self.cleaned_data["export_legend_title"]
        if export_title:
            configuration["exportLegendTitle"] = export_title
        else:
            configuration.pop("exportLegendTitle", None)

        # "Use atlas defaults" (customize off) removes the theme-level override
        # rather than copying global values, so inheritance stays distinct from
        # an explicit automatic value.
        if self.cleaned_data.get("export_legend_customize"):
            configuration["exportLegendPlacement"] = (
                self.cleaned_data.get("export_legend_placement") or AUTO
            )
            columns = self.cleaned_data.get("export_legend_columns") or AUTO
            configuration["exportLegendColumns"] = (
                AUTO if columns == AUTO else int(columns)
            )
            item_flow = normalize_item_flow(
                self.cleaned_data.get("export_legend_item_flow")
            )
            if item_flow is None:
                configuration.pop("exportLegendItemFlow", None)
            else:
                configuration["exportLegendItemFlow"] = item_flow
            width_percent = self.cleaned_data.get("export_legend_width")
            if width_percent is None:
                # A blank maximum width must keep inheriting from the atlas
                # default rather than freezing the current value.
                configuration.pop("exportLegendWidth", None)
            else:
                configuration["exportLegendWidth"] = width_percent / 100
        else:
            for key in EXPORT_LEGEND_OVERRIDE_KEYS:
                configuration.pop(key, None)
        # Retired options must never linger with a misleading effect.
        for key in LEGACY_EXPORT_LEGEND_KEYS:
            configuration.pop(key, None)

        categories = configuration.get("categories", [])
        for index, category in enumerate(categories):
            category["label"] = self.cleaned_data[f"category_{index}_label"]
            export_label = self.cleaned_data[f"category_{index}_export_label"]
            if export_label:
                category["exportLabel"] = export_label
            else:
                category.pop("exportLabel", None)

        configuration["legendCategoryOrder"] = [
            value
            for _position, value in sorted(
                (self.cleaned_data[f"{prefix}_order"], value)
                for prefix, value in self._entries()
            )
        ]

        self.instance.configuration = configuration
        self.instance.full_clean()
        self.instance.save(update_fields=["configuration", "updated_at"])
        return self.instance

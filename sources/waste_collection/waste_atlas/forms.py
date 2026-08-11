from copy import deepcopy

from django import forms

from .legend import (
    AUTO,
    EXPORT_LEGEND_OVERRIDE_KEYS,
    LEGACY_EXPORT_LEGEND_KEYS,
    normalize_columns,
    normalize_item_flow,
    normalize_placement,
    normalize_width_fraction,
)
from .models import (
    EXPORT_LEGEND_ITEM_FLOWS,
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
EXPORT_LEGEND_ITEM_FLOW_CHOICES = EXPORT_LEGEND_ITEM_FLOWS


class WasteAtlasMapConfigurationForm(forms.Form):
    """Edit the human-facing legend text without exposing raw JSON."""

    legend_title = forms.CharField(
        label="Legend title",
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
        choices=EXPORT_LEGEND_ITEM_FLOW_CHOICES,
        required=False,
        help_text=(
            "Whether entries fill one column after another or read across the "
            "columns row by row."
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

        initial = kwargs.setdefault("initial", {})
        initial.setdefault("legend_title", self._configuration.get("legendTitle", ""))
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
        initial.setdefault(
            "export_legend_item_flow",
            normalize_item_flow(self._configuration.get("exportLegendItemFlow"))
            or self._defaults.export_legend_item_flow,
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

        category_order = self._category_order()
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
            self.fields[f"category_{index}_order"] = forms.IntegerField(
                label="Order",
                initial=category_order.index(index) + 1,
                min_value=1,
                max_value=len(self._categories),
                widget=forms.NumberInput(attrs={"class": "form-control", "step": 1}),
            )

    @staticmethod
    def _is_no_collection_category(category):
        label = str(category.get("label", ""))
        return any(
            text in label
            for text in (
                "No separate biowaste collection",
                "No separate door-to-door collection",
                "No separate collection",
                "No separate green waste collection",
                "No door-to-door",
            )
        )

    def _category_order(self):
        configured_order = self._configuration.get("legendCategoryOrder")
        if isinstance(configured_order, list):
            ranks = {value: index for index, value in enumerate(configured_order)}
            return sorted(
                range(len(self._categories)),
                key=lambda index: ranks.get(
                    self._categories[index].get("value"),
                    len(ranks) + index,
                ),
            )

        normal = []
        no_collection = []
        for index, category in enumerate(self._categories):
            target = (
                no_collection if self._is_no_collection_category(category) else normal
            )
            target.append(index)
        return normal + no_collection

    @property
    def category_rows(self):
        rows = [
            (
                self[f"category_{index}_order"].value(),
                index,
                {
                    "value": category.get("value", ""),
                    "color": category.get("color", ""),
                    "label_field": self[f"category_{index}_label"],
                    "export_label_field": self[f"category_{index}_export_label"],
                    "order_field": self[f"category_{index}_order"],
                },
            )
            for index, category in enumerate(self._categories)
        ]

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
        category_positions = [
            cleaned_data.get(f"category_{index}_order")
            for index in range(len(self._categories))
        ]
        valid_positions = [
            position for position in category_positions if position is not None
        ]
        if len(valid_positions) == len(self._categories) and len(
            set(valid_positions)
        ) != len(valid_positions):
            raise forms.ValidationError("Each category position must be unique.")
        return cleaned_data

    def save(self):
        configuration = deepcopy(self._configuration)
        configuration["legendTitle"] = self.cleaned_data["legend_title"]
        configuration["legendPlacement"] = self.cleaned_data["legend_placement"]
        configuration["legendWidth"] = self.cleaned_data["legend_width"]
        configuration["legendFontSize"] = self.cleaned_data["legend_font_size"]

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
            configuration["exportLegendItemFlow"] = (
                normalize_item_flow(self.cleaned_data.get("export_legend_item_flow"))
                or self._defaults.export_legend_item_flow
            )
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
            categories[index].get("value")
            for index in sorted(
                range(len(categories)),
                key=lambda index: self.cleaned_data[f"category_{index}_order"],
            )
        ]

        self.instance.configuration = configuration
        self.instance.full_clean()
        self.instance.save(update_fields=["configuration", "updated_at"])
        return self.instance

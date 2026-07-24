from copy import deepcopy

from django import forms

LEGEND_PLACEMENT_CHOICES = (
    ("bottom-left", "Bottom left"),
    ("bottom-right", "Bottom right"),
    ("top-left", "Top left"),
    ("top-right", "Top right"),
)
EXPORT_LEGEND_PLACEMENT_CHOICES = (
    ("", "Automatic"),
    ("right", "Right"),
    ("left", "Left"),
    ("bottom", "Bottom"),
    ("bottom-right", "Bottom right"),
    ("bottom-left", "Bottom left"),
    ("top-right", "Top right"),
    ("top-left", "Top left"),
)


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
    export_legend_placement = forms.ChoiceField(
        label="Placement",
        choices=EXPORT_LEGEND_PLACEMENT_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    export_legend_width = forms.IntegerField(
        label="Maximum width (%)",
        min_value=20,
        max_value=90,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": 1}),
    )
    export_legend_columns = forms.TypedChoiceField(
        label="Columns",
        choices=((1, "1"), (2, "2"), (3, "3"), (4, "4")),
        coerce=int,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    export_legend_fit_content = forms.BooleanField(
        label="Fit width to content",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )
    export_legend_avoid_map_overlap = forms.BooleanField(
        label="Avoid map overlap",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, instance, **kwargs):
        self.instance = instance
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
            self._configuration.get("legendPlacement", "bottom-left"),
        )
        initial.setdefault("legend_width", self._configuration.get("legendWidth", 300))
        initial.setdefault(
            "legend_font_size",
            self._configuration.get("legendFontSize", 12),
        )
        initial.setdefault(
            "export_legend_placement",
            self._configuration.get("exportLegendPlacement", ""),
        )
        initial.setdefault(
            "export_legend_width",
            round(self._configuration.get("exportLegendWidth", 0.52) * 100),
        )
        initial.setdefault(
            "export_legend_columns",
            self._configuration.get("exportLegendColumns", 1),
        )
        initial.setdefault(
            "export_legend_fit_content",
            self._configuration.get("exportLegendFitContent", False),
        )
        initial.setdefault(
            "export_legend_avoid_map_overlap",
            self._configuration.get("exportLegendAvoidMapOverlap", False),
        )
        super().__init__(*args, **kwargs)

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

        export_placement = self.cleaned_data["export_legend_placement"]
        export_keys = (
            "exportLegendPlacement",
            "exportLegendWidth",
            "exportLegendColumns",
            "exportLegendFitContent",
            "exportLegendAvoidMapOverlap",
        )
        if export_placement:
            configuration["exportLegendPlacement"] = export_placement
            configuration["exportLegendWidth"] = (
                self.cleaned_data["export_legend_width"] / 100
            )
            configuration["exportLegendColumns"] = self.cleaned_data[
                "export_legend_columns"
            ]
            configuration["exportLegendFitContent"] = self.cleaned_data[
                "export_legend_fit_content"
            ]
            configuration["exportLegendAvoidMapOverlap"] = self.cleaned_data[
                "export_legend_avoid_map_overlap"
            ]
        else:
            for key in export_keys:
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

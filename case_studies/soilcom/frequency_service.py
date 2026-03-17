import re
from decimal import ROUND_HALF_UP, Decimal

CADENCE_WEEKLY = "weekly"
CADENCE_EVERY_TWO_WEEKS = "every_two_weeks"
CADENCE_EVERY_FOUR_WEEKS = "every_four_weeks"
CADENCE_MONTHLY = "monthly"
CADENCE_CUSTOM = "custom"

CADENCE_CHOICES = (
    ("", "Not used"),
    (CADENCE_WEEKLY, "Weekly"),
    (CADENCE_EVERY_TWO_WEEKS, "Every 2 weeks"),
    (CADENCE_EVERY_FOUR_WEEKS, "Every 4 weeks"),
    (CADENCE_MONTHLY, "Monthly"),
    (CADENCE_CUSTOM, "Custom annual total"),
)

CADENCE_TO_ANNUAL_COUNT = {
    CADENCE_WEEKLY: 52,
    CADENCE_EVERY_TWO_WEEKS: 26,
    CADENCE_EVERY_FOUR_WEEKS: 13,
    CADENCE_MONTHLY: 12,
}

CADENCE_DISPLAY_LABELS = {
    CADENCE_WEEKLY: "Weekly",
    CADENCE_EVERY_TWO_WEEKS: "Every 2 weeks",
    CADENCE_EVERY_FOUR_WEEKS: "Every 4 weeks",
    CADENCE_MONTHLY: "Monthly",
}

COUNT_FIELDS = ("standard", "option_1", "option_2", "option_3")
OPTION_FIELDS = COUNT_FIELDS[1:]
TIMESTEP_NAME_ALIASES = {"mai": "may"}
CADENCE_NAME_PATTERNS = {
    CADENCE_WEEKLY: re.compile(
        r"1\s+per\s+week\s+from\s+(?P<start>[^,;()]+?)\s*-\s*(?P<end>[^,;()]+)",
        re.IGNORECASE,
    ),
    CADENCE_EVERY_TWO_WEEKS: re.compile(
        r"1\s+per\s+2\s+weeks\s+from\s+(?P<start>[^,;()]+?)\s*-\s*(?P<end>[^,;()]+)",
        re.IGNORECASE,
    ),
    CADENCE_EVERY_FOUR_WEEKS: re.compile(
        r"1\s+per\s+4\s+weeks\s+from\s+(?P<start>[^,;()]+?)\s*-\s*(?P<end>[^,;()]+)",
        re.IGNORECASE,
    ),
    CADENCE_MONTHLY: re.compile(
        r"1\s+per\s+month\s+from\s+(?P<start>[^,;()]+?)\s*-\s*(?P<end>[^,;()]+)",
        re.IGNORECASE,
    ),
}


class CollectionFrequencyScheduleService:
    @classmethod
    def normalize_timestep_name(cls, value):
        if not value:
            return ""
        normalized_value = re.sub(r"\s+", " ", value.strip().lower())
        return TIMESTEP_NAME_ALIASES.get(normalized_value, normalized_value)

    @classmethod
    def cadence_hints_from_name(cls, frequency_name):
        cadence_hints = {}
        if not frequency_name:
            return cadence_hints
        for cadence, pattern in CADENCE_NAME_PATTERNS.items():
            for match in pattern.finditer(frequency_name):
                start = match.group("start")
                end = match.group("end")
                if "&" in start or "&" in end:
                    continue
                cadence_hints[
                    (
                        cls.normalize_timestep_name(start),
                        cls.normalize_timestep_name(end),
                    )
                ] = cadence
        return cadence_hints

    @classmethod
    def month_span(cls, first_timestep, last_timestep):
        if (
            not first_timestep
            or not last_timestep
            or first_timestep.distribution_id != last_timestep.distribution_id
        ):
            return 0
        return first_timestep.distribution.timestep_set.filter(
            order__gte=first_timestep.order,
            order__lte=last_timestep.order,
        ).count()

    @classmethod
    def count_from_cadence(cls, cadence, first_timestep, last_timestep):
        annual_count = CADENCE_TO_ANNUAL_COUNT.get(cadence)
        if annual_count is None:
            return None
        month_span = cls.month_span(first_timestep, last_timestep)
        if not month_span:
            return None
        derived_count = (
            Decimal(annual_count) * Decimal(month_span) / Decimal(12)
        ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return max(int(derived_count), 1)

    @classmethod
    def infer_cadence(cls, count, first_timestep, last_timestep):
        if count in (None, ""):
            return ""
        count = int(count)
        matches = [
            cadence
            for cadence in CADENCE_TO_ANNUAL_COUNT
            if cls.count_from_cadence(cadence, first_timestep, last_timestep) == count
        ]
        if len(matches) == 1:
            return matches[0]
        return CADENCE_CUSTOM

    @classmethod
    def populate_counts_from_cadences(cls, cleaned_data):
        first_timestep = cleaned_data.get("first_timestep")
        last_timestep = cleaned_data.get("last_timestep")
        for field_name in COUNT_FIELDS:
            cadence_field = f"{field_name}_cadence"
            cadence = cleaned_data.get(cadence_field)
            value = cleaned_data.get(field_name)
            if cadence and cadence != CADENCE_CUSTOM:
                cleaned_data[field_name] = cls.count_from_cadence(
                    cadence, first_timestep, last_timestep
                )
            elif cadence == CADENCE_CUSTOM:
                cleaned_data[field_name] = value
            elif value not in (None, ""):
                cleaned_data[cadence_field] = CADENCE_CUSTOM
                cleaned_data[field_name] = value
            else:
                cleaned_data[cadence_field] = ""
                cleaned_data[field_name] = None
        return cleaned_data

    @classmethod
    def rows_from_formset(cls, formset):
        rows = []
        for form in formset.forms:
            if not getattr(form, "cleaned_data", None):
                continue
            rows.append(
                {
                    field_name: form.cleaned_data.get(field_name)
                    for field_name in (
                        "distribution",
                        "first_timestep",
                        "last_timestep",
                        *COUNT_FIELDS,
                        *(f"{field_name}_cadence" for field_name in COUNT_FIELDS),
                    )
                }
            )
        return rows

    @classmethod
    def rows_from_frequency(cls, frequency):
        rows = []
        cadence_hints = cls.cadence_hints_from_name(frequency.name)
        options_qs = frequency.collectioncountoptions_set.select_related(
            "season__distribution",
            "season__first_timestep",
            "season__last_timestep",
        ).order_by("season__first_timestep__order")
        for options in options_qs:
            cadence_hint = cadence_hints.get(
                (
                    cls.normalize_timestep_name(options.season.first_timestep.name),
                    cls.normalize_timestep_name(options.season.last_timestep.name),
                )
            )
            row = {
                "distribution": options.season.distribution,
                "first_timestep": options.season.first_timestep,
                "last_timestep": options.season.last_timestep,
            }
            for field_name in COUNT_FIELDS:
                value = getattr(options, field_name)
                row[field_name] = value
                if field_name == "standard" and cadence_hint and value is not None:
                    row[f"{field_name}_cadence"] = cadence_hint
                else:
                    row[f"{field_name}_cadence"] = cls.infer_cadence(
                        value,
                        options.season.first_timestep,
                        options.season.last_timestep,
                    )
            rows.append(row)
        return rows

    @classmethod
    def frequency_type(cls, rows):
        has_options = any(
            row.get(field_name) is not None
            for row in rows
            for field_name in OPTION_FIELDS
        )
        if len(rows) > 1:
            return "Fixed-Seasonal" if has_options else "Seasonal"
        return "Fixed-Flexible" if has_options else "Fixed"

    @classmethod
    def segment_label(cls, first_timestep, last_timestep):
        if not first_timestep or not last_timestep:
            return "Unspecified"
        if first_timestep.name == "January" and last_timestep.name == "December":
            return "Year-round"
        return f"{first_timestep.name}-{last_timestep.name}"

    @classmethod
    def segment_display_label(cls, first_timestep, last_timestep):
        if not first_timestep or not last_timestep:
            return "Unspecified period"
        if first_timestep.name == "January" and last_timestep.name == "December":
            return "All year"
        return f"{first_timestep.name} to {last_timestep.name}"

    @classmethod
    def count_display_label(cls, count, first_timestep, last_timestep):
        if count in (None, ""):
            return "Not specified"
        count = int(count)
        if (
            first_timestep
            and last_timestep
            and first_timestep.name == "January"
            and last_timestep.name == "December"
        ):
            suffix = "per year"
        else:
            suffix = "during this period"
        noun = "collection" if count == 1 else "collections"
        return f"{count} {noun} {suffix}"

    @classmethod
    def display_label(cls, cadence, count, first_timestep, last_timestep):
        if cadence and cadence != CADENCE_CUSTOM:
            cadence_label = CADENCE_DISPLAY_LABELS.get(cadence)
            if cadence_label:
                return cadence_label
        return cls.count_display_label(count, first_timestep, last_timestep)

    @classmethod
    def display_rows(cls, frequency):
        rows = cls.rows_from_frequency(frequency)
        display_rows = []
        for row in rows:
            first_timestep = row.get("first_timestep")
            last_timestep = row.get("last_timestep")
            display_rows.append(
                {
                    "segment": cls.segment_display_label(first_timestep, last_timestep),
                    "standard": cls.display_label(
                        row.get("standard_cadence"),
                        row.get("standard"),
                        first_timestep,
                        last_timestep,
                    ),
                    "options": [
                        cls.display_label(
                            row.get(f"{field_name}_cadence"),
                            row.get(field_name),
                            first_timestep,
                            last_timestep,
                        )
                        for field_name in OPTION_FIELDS
                        if row.get(field_name) is not None
                    ],
                }
            )
        return display_rows

    @classmethod
    def cadence_or_count_label(cls, cadence, count):
        if count in (None, ""):
            return "unspecified"
        if cadence and cadence != CADENCE_CUSTOM:
            return dict(CADENCE_CHOICES)[cadence].lower()
        return f"custom ({count} per year)"

    @classmethod
    def summary(cls, rows):
        summaries = []
        for row in rows:
            label = cls.segment_label(
                row.get("first_timestep"), row.get("last_timestep")
            )
            standard_label = cls.cadence_or_count_label(
                row.get("standard_cadence"), row.get("standard")
            )
            option_values = [
                cls.cadence_or_count_label(
                    row.get(f"{field_name}_cadence"), row.get(field_name)
                )
                for field_name in OPTION_FIELDS
                if row.get(field_name) is not None
            ]
            segment_summary = f"{label}: {standard_label}"
            if option_values:
                segment_summary += f"; optional {' / '.join(option_values)}"
            summaries.append(segment_summary)
        return "; ".join(summaries)

    @classmethod
    def canonical_name(cls, rows, frequency_type):
        if not rows:
            return frequency_type
        if len(rows) == 1 and not any(
            rows[0].get(field_name) is not None for field_name in OPTION_FIELDS
        ):
            standard = rows[0].get("standard")
            if standard is not None:
                return f"{frequency_type}; {standard} per year"
        parts = []
        for row in rows:
            segment_label = cls.segment_label(
                row.get("first_timestep"), row.get("last_timestep")
            )
            standard = row.get("standard")
            segment = f"{segment_label} {standard if standard is not None else 'unspecified'} per year"
            option_values = [
                str(row.get(field_name))
                for field_name in OPTION_FIELDS
                if row.get(field_name) is not None
            ]
            if option_values:
                segment += f" (options {'/'.join(option_values)} per year)"
            parts.append(segment)
        return f"{frequency_type}; {'; '.join(parts)}"

    @classmethod
    def initial_row(cls, distribution, first_timestep, last_timestep):
        return {
            "distribution": distribution,
            "first_timestep": first_timestep,
            "last_timestep": last_timestep,
            **dict.fromkeys(COUNT_FIELDS),
            **{f"{field_name}_cadence": "" for field_name in COUNT_FIELDS},
        }

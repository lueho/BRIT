from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

LEFT_MAP_LABELS = (
    "ET",
    "Fyrfackskärl",
    "Ingen utsortering",
    "Optisk sortering",
    "Separata kärl",
    "Tvådelade kärl",
)
RIGHT_MAP_LABELS = ("Bioplast", "ET", "Papper", "Plastpåse")
LEFT_LABEL_TO_BIN_CONFIGURATION = {
    "Fyrfackskärl": "Four compartments bin",
    "Optisk sortering": "Optical bag sorting",
    "Separata kärl": "Separate bins",
    "Tvådelade kärl": "Two compartments bin",
}
RIGHT_LABEL_TO_BAG_MATERIAL = {
    "Bioplast": "Collection Support Item: Biodegradable plastic bags",
    "Papper": "Collection Support Item: Paper bags",
    "Plastpåse": "Collection Support Item: Plastic bags",
}
NO_COLLECTION_LABELS = frozenset({"ET", "Ingen utsortering"})
LEFT_DISTANCE_LIMIT = 4000
RIGHT_DISTANCE_LIMIT = 5000
SEARCH_SCALE_MULTIPLIERS = (0.94, 0.97, 1.0, 1.03, 1.06)
SEARCH_OFFSETS = tuple(range(-18, 19, 6))
MAP_PROJECTION_SRID = 3006
MIN_CLASSIFIED_PIXELS = 3
TRUTHY_VALUES = {"1", "true", "yes", "y"}
CSV_FIELDNAMES = [
    "lau_id",
    "municipality_name",
    "sorting_label",
    "bin_configuration",
    "sorting_confidence",
    "sorting_pixels",
    "bag_label",
    "bag_material",
    "bag_confidence",
    "bag_pixels",
    "collection_system",
    "no_collection",
    "needs_manual_review",
    "review_reasons",
]
REVIEW_FIELDNAMES = [
    field_name
    for field_name in CSV_FIELDNAMES
    if field_name not in {"lau_id", "municipality_name"}
]
RAW_FILE_FORMAT = "sweden-2024-map-raw"
RAW_FILE_VERSION = 1


@dataclass(frozen=True)
class MapAssignment:
    label: str
    classified_pixels: int
    confidence: float


@dataclass(frozen=True)
class MapTransform:
    scale_multiplier: float
    dx: int
    dy: int
    assigned_count: int


@dataclass(frozen=True)
class RawMapRow:
    lau_id: str
    municipality_name: str
    sorting_assignment: MapAssignment | None
    bag_assignment: MapAssignment | None
    reviewed_fields: dict[str, str] | None = None


@dataclass(frozen=True)
class RawMapData:
    rows: list[RawMapRow]
    left_transform: MapTransform
    right_transform: MapTransform


@dataclass(frozen=True)
class PreparedMapData:
    rows: list[dict[str, str]]
    left_transform: MapTransform
    right_transform: MapTransform


@dataclass(frozen=True)
class _ProjectedRegion:
    lau_id: str
    municipality_name: str
    polygons: list[list[tuple[float, float]]]


class Sweden2024MapDataError(Exception):
    pass


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in TRUTHY_VALUES


def _rgb_from_fill(fill) -> tuple[int, int, int]:
    return tuple(int(round(channel * 255)) for channel in fill)


def _iter_polygons(geom):
    return list(geom) if geom.geom_type == "MultiPolygon" else [geom]


def _coord_xy(coord) -> tuple[float, float]:
    if len(coord) >= 2 and isinstance(coord[0], int | float):
        return float(coord[0]), float(coord[1])
    if coord and isinstance(coord[0], tuple | list):
        return float(coord[0][0]), float(coord[0][1])
    raise TypeError(coord)


def _nearest_label(
    rgb: tuple[int, int, int], legend: dict[str, tuple[int, int, int]]
) -> tuple[str, int]:
    best_label = ""
    best_distance = 10**12
    for label, target in legend.items():
        distance = sum(
            (component - target_component) ** 2
            for component, target_component in zip(rgb, target, strict=False)
        )
        if distance < best_distance:
            best_distance = distance
            best_label = label
    return best_label, best_distance


def _legend_from_drawings(
    page,
) -> tuple[dict[str, tuple[int, int, int]], dict[str, tuple[int, int, int]]]:
    drawings = [
        drawing
        for drawing in page.get_drawings()
        if drawing.get("fill") is not None and drawing.get("rect") is not None
    ]
    left_drawings = sorted(
        [drawing for drawing in drawings if drawing["rect"].x0 < 200],
        key=lambda drawing: drawing["rect"].y0,
    )
    right_drawings = sorted(
        [drawing for drawing in drawings if drawing["rect"].x0 >= 200],
        key=lambda drawing: drawing["rect"].y0,
    )
    if len(left_drawings) < len(LEFT_MAP_LABELS) or len(right_drawings) < len(
        RIGHT_MAP_LABELS
    ):
        raise Sweden2024MapDataError("Could not extract page-24 legend swatches.")
    left_legend = {
        label: _rgb_from_fill(drawing["fill"])
        for label, drawing in zip(LEFT_MAP_LABELS, left_drawings, strict=False)
    }
    right_legend = {
        label: _rgb_from_fill(drawing["fill"])
        for label, drawing in zip(RIGHT_MAP_LABELS, right_drawings, strict=False)
    }
    return left_legend, right_legend


def _extract_page24_assets(pdf_path: Path):
    try:
        import fitz
        from PIL import Image
    except ImportError as exc:
        raise Sweden2024MapDataError(
            "PyMuPDF and Pillow are required to parse the Sweden 2024 map pages."
        ) from exc

    pdf = fitz.open(pdf_path)
    page = pdf[23]
    images = page.get_images(full=True)
    if len(images) < 2:
        raise Sweden2024MapDataError("Could not find both page-24 map images.")
    left_image = Image.frombytes(
        "RGB",
        [images[0][2], images[0][3]],
        fitz.Pixmap(pdf, images[0][0]).samples,
    ).convert("RGB")
    right_image = Image.frombytes(
        "RGB",
        [images[1][2], images[1][3]],
        fitz.Pixmap(pdf, images[1][0]).samples,
    ).convert("RGB")
    left_legend, right_legend = _legend_from_drawings(page)
    return left_image, right_image, left_legend, right_legend


def _load_projected_regions() -> (
    tuple[list[_ProjectedRegion], tuple[float, float, float, float]]
):
    from maps.models import LauRegion

    regions = []
    min_x = float("inf")
    min_y = float("inf")
    max_x = float("-inf")
    max_y = float("-inf")
    queryset = (
        LauRegion.objects.filter(lau_id__regex=r"^[0-9]{4}$")
        .exclude(borders__geom__isnull=True)
        .order_by("lau_id")
    )
    for region in queryset:
        geom = region.borders.geom.clone()
        geom.transform(MAP_PROJECTION_SRID)
        polygons = []
        for polygon in _iter_polygons(geom):
            polygons.append([
                _coord_xy(coord) for coord in polygon.exterior_ring.coords
            ])
        regions.append(
            _ProjectedRegion(
                lau_id=(region.lau_id or "").zfill(4),
                municipality_name=(region.lau_name or region.name or "").strip(),
                polygons=polygons,
            )
        )
        geom_min_x, geom_min_y, geom_max_x, geom_max_y = geom.extent
        min_x = min(min_x, geom_min_x)
        min_y = min(min_y, geom_min_y)
        max_x = max(max_x, geom_max_x)
        max_y = max(max_y, geom_max_y)
    if len(regions) != 290:
        raise Sweden2024MapDataError(
            f"Expected 290 Swedish LAU regions, found {len(regions)}."
        )
    return regions, (min_x, min_y, max_x, max_y)


def _classify_with_transform(
    *,
    regions: list[_ProjectedRegion],
    bounds: tuple[float, float, float, float],
    image,
    legend: dict[str, tuple[int, int, int]],
    transform: MapTransform,
    max_distance_sq: int,
    min_classified_pixels: int,
) -> dict[str, MapAssignment]:
    from PIL import Image, ImageDraw

    min_x, min_y, max_x, max_y = bounds
    base_scale = min(image.size[0] / (max_x - min_x), image.size[1] / (max_y - min_y))
    scale = base_scale * transform.scale_multiplier
    offset_x = (image.size[0] - (max_x - min_x) * scale) / 2 + transform.dx
    offset_y = (image.size[1] - (max_y - min_y) * scale) / 2 + transform.dy

    def pixel_x(value: float) -> float:
        return offset_x + (value - min_x) * scale

    def pixel_y(value: float) -> float:
        return offset_y + (max_y - value) * scale

    assignments: dict[str, MapAssignment] = {}
    for region in regions:
        mask = Image.new("1", image.size, 0)
        drawer = ImageDraw.Draw(mask)
        for polygon in region.polygons:
            points = [(pixel_x(x), pixel_y(y)) for x, y in polygon]
            if len(points) >= 3:
                drawer.polygon(points, fill=1)
        bbox = mask.getbbox()
        if not bbox:
            continue
        color_counts: Counter[str] = Counter()
        image_pixels = list(image.crop(bbox).getdata())
        mask_pixels = list(mask.crop(bbox).getdata())
        for rgb, is_inside in zip(image_pixels, mask_pixels, strict=False):
            if not is_inside:
                continue
            label, distance = _nearest_label(rgb, legend)
            if distance <= max_distance_sq:
                color_counts[label] += 1
        classified_pixels = sum(color_counts.values())
        if classified_pixels < min_classified_pixels:
            continue
        label, count = color_counts.most_common(1)[0]
        assignments[region.lau_id] = MapAssignment(
            label=label,
            classified_pixels=classified_pixels,
            confidence=count / classified_pixels,
        )
    return assignments


def _best_assignments(
    *,
    regions: list[_ProjectedRegion],
    bounds: tuple[float, float, float, float],
    image,
    legend: dict[str, tuple[int, int, int]],
    max_distance_sq: int,
    min_classified_pixels: int,
) -> tuple[dict[str, MapAssignment], MapTransform]:
    best_assignments: dict[str, MapAssignment] = {}
    best_transform = MapTransform(1.0, 0, 0, 0)
    for scale_multiplier in SEARCH_SCALE_MULTIPLIERS:
        for dx in SEARCH_OFFSETS:
            for dy in SEARCH_OFFSETS:
                candidate_transform = MapTransform(scale_multiplier, dx, dy, 0)
                assignments = _classify_with_transform(
                    regions=regions,
                    bounds=bounds,
                    image=image,
                    legend=legend,
                    transform=candidate_transform,
                    max_distance_sq=max_distance_sq,
                    min_classified_pixels=min_classified_pixels,
                )
                if len(assignments) > len(best_assignments):
                    best_assignments = assignments
                    best_transform = MapTransform(
                        scale_multiplier=scale_multiplier,
                        dx=dx,
                        dy=dy,
                        assigned_count=len(assignments),
                    )
    return best_assignments, best_transform


def _assignment_to_dict(assignment: MapAssignment | None) -> dict[str, object] | None:
    if assignment is None:
        return None
    return {
        "label": assignment.label,
        "classified_pixels": assignment.classified_pixels,
        "confidence": assignment.confidence,
    }


def _assignment_from_dict(data: dict[str, object] | None) -> MapAssignment | None:
    if not data:
        return None
    return MapAssignment(
        label=str(data.get("label") or ""),
        classified_pixels=int(data.get("classified_pixels") or 0),
        confidence=float(data.get("confidence") or 0.0),
    )


def _transform_from_dict(data: dict[str, object] | None) -> MapTransform:
    data = data or {}
    return MapTransform(
        scale_multiplier=float(data.get("scale_multiplier") or 1.0),
        dx=int(data.get("dx") or 0),
        dy=int(data.get("dy") or 0),
        assigned_count=int(data.get("assigned_count") or 0),
    )


def build_prepared_row(
    *,
    lau_id: str,
    municipality_name: str,
    sorting_assignment: MapAssignment | None,
    bag_assignment: MapAssignment | None,
    reviewed_fields: dict[str, str] | None = None,
) -> dict[str, str]:
    reviewed_fields = reviewed_fields or {}
    sorting_label = sorting_assignment.label if sorting_assignment else ""
    bag_label = bag_assignment.label if bag_assignment else ""
    detected_no_collection = sorting_label in NO_COLLECTION_LABELS or bag_label == "ET"
    if "no_collection" in reviewed_fields:
        no_collection = _is_truthy(reviewed_fields.get("no_collection"))
    else:
        no_collection = detected_no_collection
    detected_bin_configuration = ""
    detected_bag_material = ""
    if not detected_no_collection:
        detected_bin_configuration = LEFT_LABEL_TO_BIN_CONFIGURATION.get(
            sorting_label, ""
        )
        detected_bag_material = RIGHT_LABEL_TO_BAG_MATERIAL.get(bag_label, "")
    reasons: list[str] = []
    if detected_no_collection:
        if sorting_label == "ET" and bag_label not in ("", "ET"):
            reasons.append("sorting ET disagrees with bag map")
        if sorting_label == "Ingen utsortering" and bag_label not in ("", "ET"):
            reasons.append("no-collection sorting disagrees with bag map")
        if bag_label == "ET" and sorting_label not in ("", "ET", "Ingen utsortering"):
            reasons.append("bag ET disagrees with sorting map")
    else:
        if not detected_bin_configuration:
            reasons.append("sorting method unresolved")
        if not detected_bag_material:
            reasons.append("bag material unresolved")
    if sorting_assignment and sorting_assignment.confidence < 0.55:
        reasons.append("sorting confidence below 0.55")
    if bag_assignment and bag_assignment.confidence < 0.55:
        reasons.append("bag confidence below 0.55")
    if not sorting_assignment and not no_collection:
        reasons.append("sorting map unclassified")
    if not bag_assignment and not no_collection:
        reasons.append("bag map unclassified")
    bin_configuration = (
        reviewed_fields.get("bin_configuration", "").strip()
        if "bin_configuration" in reviewed_fields
        else detected_bin_configuration
    )
    bag_material = (
        reviewed_fields.get("bag_material", "").strip()
        if "bag_material" in reviewed_fields
        else detected_bag_material
    )
    collection_system = (
        reviewed_fields.get("collection_system", "").strip()
        if "collection_system" in reviewed_fields
        else ("No separate collection" if no_collection else "Door to door")
    )
    if "needs_manual_review" in reviewed_fields:
        needs_manual_review = (
            "1" if _is_truthy(reviewed_fields.get("needs_manual_review")) else "0"
        )
    else:
        needs_manual_review = "1" if reasons else "0"
    if "review_reasons" in reviewed_fields:
        review_reasons = reviewed_fields.get("review_reasons", "")
    else:
        review_reasons = "; ".join(reasons)
    return {
        "lau_id": lau_id,
        "municipality_name": municipality_name,
        "sorting_label": sorting_label,
        "bin_configuration": bin_configuration,
        "sorting_confidence": (
            f"{sorting_assignment.confidence:.3f}" if sorting_assignment else ""
        ),
        "sorting_pixels": (
            str(sorting_assignment.classified_pixels) if sorting_assignment else "0"
        ),
        "bag_label": bag_label,
        "bag_material": bag_material,
        "bag_confidence": f"{bag_assignment.confidence:.3f}" if bag_assignment else "",
        "bag_pixels": (
            str(bag_assignment.classified_pixels) if bag_assignment else "0"
        ),
        "collection_system": collection_system,
        "no_collection": "1" if no_collection else "0",
        "needs_manual_review": needs_manual_review,
        "review_reasons": review_reasons,
    }


def build_prepared_rows(raw_map_data: RawMapData) -> list[dict[str, str]]:
    return [
        build_prepared_row(
            lau_id=row.lau_id,
            municipality_name=row.municipality_name,
            sorting_assignment=row.sorting_assignment,
            bag_assignment=row.bag_assignment,
            reviewed_fields=row.reviewed_fields,
        )
        for row in raw_map_data.rows
    ]


def _review_fields_from_row(raw_row: RawMapRow) -> dict[str, str]:
    prepared_row = build_prepared_row(
        lau_id=raw_row.lau_id,
        municipality_name=raw_row.municipality_name,
        sorting_assignment=raw_row.sorting_assignment,
        bag_assignment=raw_row.bag_assignment,
        reviewed_fields=raw_row.reviewed_fields,
    )
    return {field_name: prepared_row[field_name] for field_name in REVIEW_FIELDNAMES}


def extract_raw_map_data(pdf_path: str | Path) -> RawMapData:
    pdf_path = Path(pdf_path)
    left_image, right_image, left_legend, right_legend = _extract_page24_assets(
        pdf_path
    )
    regions, bounds = _load_projected_regions()
    left_assignments, left_transform = _best_assignments(
        regions=regions,
        bounds=bounds,
        image=left_image,
        legend=left_legend,
        max_distance_sq=LEFT_DISTANCE_LIMIT,
        min_classified_pixels=MIN_CLASSIFIED_PIXELS,
    )
    right_assignments, right_transform = _best_assignments(
        regions=regions,
        bounds=bounds,
        image=right_image,
        legend=right_legend,
        max_distance_sq=RIGHT_DISTANCE_LIMIT,
        min_classified_pixels=MIN_CLASSIFIED_PIXELS,
    )
    rows = [
        RawMapRow(
            lau_id=region.lau_id,
            municipality_name=region.municipality_name,
            sorting_assignment=left_assignments.get(region.lau_id),
            bag_assignment=right_assignments.get(region.lau_id),
        )
        for region in regions
    ]
    return RawMapData(
        rows=rows,
        left_transform=left_transform,
        right_transform=right_transform,
    )


def extract_prepared_map_data(pdf_path: str | Path) -> PreparedMapData:
    raw_map_data = extract_raw_map_data(pdf_path)
    return PreparedMapData(
        rows=build_prepared_rows(raw_map_data),
        left_transform=raw_map_data.left_transform,
        right_transform=raw_map_data.right_transform,
    )


def write_raw_map_data(raw_map_data: RawMapData, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": RAW_FILE_FORMAT,
        "version": RAW_FILE_VERSION,
        "left_transform": {
            "scale_multiplier": raw_map_data.left_transform.scale_multiplier,
            "dx": raw_map_data.left_transform.dx,
            "dy": raw_map_data.left_transform.dy,
            "assigned_count": raw_map_data.left_transform.assigned_count,
        },
        "right_transform": {
            "scale_multiplier": raw_map_data.right_transform.scale_multiplier,
            "dx": raw_map_data.right_transform.dx,
            "dy": raw_map_data.right_transform.dy,
            "assigned_count": raw_map_data.right_transform.assigned_count,
        },
        "rows": [
            {
                "lau_id": row.lau_id,
                "municipality_name": row.municipality_name,
                "sorting_assignment": _assignment_to_dict(row.sorting_assignment),
                "bag_assignment": _assignment_to_dict(row.bag_assignment),
                **_review_fields_from_row(row),
            }
            for row in raw_map_data.rows
        ],
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_reviewed_map_rows(
    rows: list[dict[str, str]], output_path: str | Path
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def write_prepared_map_rows(
    rows: list[dict[str, str]], output_path: str | Path
) -> None:
    write_reviewed_map_rows(rows, output_path)


def _load_raw_payload(raw_path: str | Path) -> dict[str, object]:
    raw_path = Path(raw_path)
    with raw_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("format") != RAW_FILE_FORMAT:
        raise Sweden2024MapDataError(
            f"Expected {RAW_FILE_FORMAT} format, found {payload.get("format")}."
        )
    if payload.get("version") != RAW_FILE_VERSION:
        raise Sweden2024MapDataError(
            f"Expected version {RAW_FILE_VERSION}, found {payload.get("version")}."
        )
    return payload


def _raw_row_from_payload_row(row: dict[str, object]) -> RawMapRow:
    reviewed_fields = {
        field_name: "" if row.get(field_name) is None else str(row.get(field_name))
        for field_name in REVIEW_FIELDNAMES
        if field_name in row
    }
    return RawMapRow(
        lau_id=str(row.get("lau_id") or "").strip().zfill(4),
        municipality_name=str(row.get("municipality_name") or "").strip(),
        sorting_assignment=_assignment_from_dict(row.get("sorting_assignment")),
        bag_assignment=_assignment_from_dict(row.get("bag_assignment")),
        reviewed_fields=reviewed_fields or None,
    )


def _reviewed_row_from_raw_payload_row(row: dict[str, object]) -> dict[str, str]:
    if any(field_name in row for field_name in REVIEW_FIELDNAMES):
        reviewed_row = {
            "lau_id": str(row.get("lau_id") or "").strip().zfill(4),
            "municipality_name": str(row.get("municipality_name") or "").strip(),
        }
        for field_name in REVIEW_FIELDNAMES:
            value = row.get(field_name, "")
            reviewed_row[field_name] = "" if value is None else str(value)
        return reviewed_row
    raw_row = _raw_row_from_payload_row(row)
    return build_prepared_row(
        lau_id=raw_row.lau_id,
        municipality_name=raw_row.municipality_name,
        sorting_assignment=raw_row.sorting_assignment,
        bag_assignment=raw_row.bag_assignment,
        reviewed_fields=raw_row.reviewed_fields,
    )


def load_raw_map_data(raw_path: str | Path) -> RawMapData:
    payload = _load_raw_payload(raw_path)
    rows = [_raw_row_from_payload_row(row) for row in payload.get("rows") or []]
    return RawMapData(
        rows=rows,
        left_transform=_transform_from_dict(payload.get("left_transform")),
        right_transform=_transform_from_dict(payload.get("right_transform")),
    )


def _prepared_rows_to_map_details(
    rows: list[dict[str, str]],
    *,
    include_manual_review: bool = False,
) -> dict[str, dict[str, object]]:
    details: dict[str, dict[str, object]] = {}
    for row in rows:
        lau_id = (row.get("lau_id") or "").strip().zfill(4)
        needs_manual_review = _is_truthy(row.get("needs_manual_review"))
        if not lau_id or (needs_manual_review and not include_manual_review):
            continue
        review_reasons = [
            reason.strip()
            for reason in str(row.get("review_reasons") or "").split("|")
            if reason.strip()
        ]
        if _is_truthy(row.get("no_collection")):
            details[lau_id] = {
                "no_collection": True,
                "bin_configuration": None,
                "bag_material": None,
            }
            if include_manual_review:
                details[lau_id]["needs_manual_review"] = needs_manual_review
                details[lau_id]["review_reasons"] = review_reasons
            continue
        bin_configuration = (row.get("bin_configuration") or "").strip() or None
        bag_material = (row.get("bag_material") or "").strip() or None
        if not (bin_configuration or bag_material or include_manual_review):
            continue
        details[lau_id] = {
            "no_collection": False,
            "bin_configuration": bin_configuration,
            "bag_material": bag_material,
        }
        if include_manual_review:
            details[lau_id]["needs_manual_review"] = needs_manual_review
            details[lau_id]["review_reasons"] = review_reasons
    return details


def load_raw_map_details(raw_path: str | Path) -> dict[str, dict[str, object]]:
    payload = _load_raw_payload(raw_path)
    reviewed_rows = [
        _reviewed_row_from_raw_payload_row(row) for row in payload.get("rows") or []
    ]
    return _prepared_rows_to_map_details(reviewed_rows)


def load_raw_map_import_details(raw_path: str | Path) -> dict[str, dict[str, object]]:
    payload = _load_raw_payload(raw_path)
    reviewed_rows = [
        _reviewed_row_from_raw_payload_row(row) for row in payload.get("rows") or []
    ]
    return _prepared_rows_to_map_details(reviewed_rows, include_manual_review=True)


def load_reviewed_map_details(csv_path: str | Path) -> dict[str, dict[str, object]]:
    csv_path = Path(csv_path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return _prepared_rows_to_map_details(list(csv.DictReader(handle)))


def load_reviewed_map_import_details(
    csv_path: str | Path,
) -> dict[str, dict[str, object]]:
    csv_path = Path(csv_path)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return _prepared_rows_to_map_details(
            list(csv.DictReader(handle)), include_manual_review=True
        )


def load_prepared_map_details(csv_path: str | Path) -> dict[str, dict[str, object]]:
    return load_reviewed_map_details(csv_path)


def load_map_details(map_path: str | Path) -> dict[str, dict[str, object]]:
    map_path = Path(map_path)
    if map_path.suffix.lower() == ".json":
        return load_raw_map_details(map_path)
    return load_reviewed_map_details(map_path)


def load_map_import_details(map_path: str | Path) -> dict[str, dict[str, object]]:
    map_path = Path(map_path)
    if map_path.suffix.lower() == ".json":
        return load_raw_map_import_details(map_path)
    return load_reviewed_map_import_details(map_path)

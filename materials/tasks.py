"""Celery tasks for materials app."""

import logging

from celery import shared_task

from utils.file_export.storages import TempUserFileDownloadStorage

from .models import ComponentMeasurement, Sample
from .renderers import SampleMeasurementsXLSXRenderer

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="export_sample_measurements_to_excel")
def export_sample_measurements_to_excel(self, sample_id):
    """
    Export a sample's component measurements to an Excel file matching the import format.

    Args:
        sample_id: Primary key of the Sample to export

    Returns:
        URL to download the generated Excel file
    """
    logger.info("Starting export for sample %s", sample_id)

    try:
        sample = (
            Sample.objects.select_related("material", "series", "owner")
            .prefetch_related("sources")
            .get(pk=sample_id)
        )
    except Sample.DoesNotExist:
        logger.error("Sample %s not found", sample_id)
        return {"status": "error", "error": f"Sample {sample_id} not found"}

    measurements = (
        ComponentMeasurement.objects.filter(sample=sample)
        .select_related(
            "group",
            "component",
            "basis_component",
            "analytical_method",
            "unit",
        )
        .prefetch_related("sources")
        .order_by("group__name", "component__name")
    )

    def progress_callback(percent, status):
        self.update_state(
            state="PROGRESS",
            meta={
                "percent": percent,
                "status": status,
            },
        )

    # Render Excel file
    renderer = SampleMeasurementsXLSXRenderer(
        sample=sample,
        measurements=measurements,
        progress_callback=progress_callback,
    )
    buffer = renderer.render()

    # Save to storage
    storage = TempUserFileDownloadStorage()
    file_name = f"sample_{sample.pk}_{sample.name[:20]}_{self.request.id}.xlsx"
    file_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in file_name)

    with storage.open(file_name, "wb") as f:
        f.write(buffer.getvalue())

    url = storage.url(file_name)
    logger.info("Export complete for sample %s: %s", sample_id, url)

    return {"status": "success", "url": url}

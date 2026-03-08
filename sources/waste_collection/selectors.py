from case_studies.soilcom.models import Collection


def empty_collection_queryset():
    return Collection.objects.none()


def published_collection_count():
    return Collection.objects.filter(publication_status="published").count()

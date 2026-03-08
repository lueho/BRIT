from case_studies.soilcom.models import Collection


def published_collection_count():
    return Collection.objects.filter(publication_status="published").count()

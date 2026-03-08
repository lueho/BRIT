from case_studies.flexibi_nantes.models import Greenhouse


def published_greenhouse_count():
    return Greenhouse.objects.filter(publication_status="published").count()

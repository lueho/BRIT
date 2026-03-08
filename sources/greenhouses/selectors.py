from sources.greenhouses.models import Greenhouse


def published_greenhouse_count():
    return Greenhouse.objects.filter(publication_status="published").count()

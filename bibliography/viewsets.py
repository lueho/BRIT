from utils.viewsets import AutoPermModelViewSet

from .filters import SourceModelFilterSet
from .models import Author, Licence, Source
from .serializers import AuthorModelSerializer, LicenceModelSerializer, SourceModelSerializer


class AuthorViewSet(AutoPermModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorModelSerializer
    custom_permission_required = {
        'list': None,
        'retrieve': None,
    }


class LicenceViewSet(AutoPermModelViewSet):
    queryset = Licence.objects.all()
    serializer_class = LicenceModelSerializer
    custom_permission_required = {
        'list': None,
        'retrieve': None,
    }


class SourceViewSet(AutoPermModelViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceModelSerializer
    filterset_class = SourceModelFilterSet
    custom_permission_required = {
        'list': None,
        'retrieve': None,
    }

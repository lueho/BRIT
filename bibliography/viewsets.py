from utils.object_management.viewsets import UserCreatedObjectViewSet

from .filters import SourceModelFilterSet
from .models import Author, Licence, Source
from .serializers import (
    AuthorModelSerializer,
    LicenceModelSerializer,
    SourceModelSerializer,
)


class AuthorViewSet(UserCreatedObjectViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorModelSerializer


class LicenceViewSet(UserCreatedObjectViewSet):
    queryset = Licence.objects.all()
    serializer_class = LicenceModelSerializer


class SourceViewSet(UserCreatedObjectViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceModelSerializer
    filterset_class = SourceModelFilterSet
    http_method_names = ["get", "head", "options"]

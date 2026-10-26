from rest_framework.permissions import DjangoModelPermissionsOrAnonReadOnly
from rest_framework.viewsets import ModelViewSet

from utils.object_management.viewsets import UserCreatedObjectViewSet

from .filters import SourceModelFilterSet
from .models import Author, Licence, Source
from .serializers import (
    AuthorModelSerializer,
    LicenceModelSerializer,
    SourceModelSerializer,
)


class AuthorViewSet(ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorModelSerializer
    permission_classes = [DjangoModelPermissionsOrAnonReadOnly]


class LicenceViewSet(ModelViewSet):
    queryset = Licence.objects.all()
    serializer_class = LicenceModelSerializer
    permission_classes = [DjangoModelPermissionsOrAnonReadOnly]


class SourceViewSet(UserCreatedObjectViewSet):
    queryset = Source.objects.all()
    serializer_class = SourceModelSerializer
    filterset_class = SourceModelFilterSet
    http_method_names = ["get", "head", "options"]

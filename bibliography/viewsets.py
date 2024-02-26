from utils.viewsets import AutoPermModelViewSet

from .models import Author, Licence
from .serializers import AuthorModelSerializer, LicenceModelSerializer


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

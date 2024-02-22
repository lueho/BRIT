from utils.viewsets import AutoPermModelViewSet

from .models import Author
from .serializers import AuthorModelSerializer


class AuthorViewSet(AutoPermModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorModelSerializer
    custom_permission_required = {
        'list': None,
        'retrieve': None,
    }

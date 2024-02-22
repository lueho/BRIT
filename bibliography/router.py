from rest_framework.routers import DefaultRouter

from .viewsets import AuthorViewSet

router = DefaultRouter()
router.register('authors', AuthorViewSet, basename='api-author')

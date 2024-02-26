from rest_framework.routers import DefaultRouter

from .viewsets import (AuthorViewSet, LicenceViewSet)

router = DefaultRouter()
router.register('authors', AuthorViewSet, basename='api-author')
router.register('licences', LicenceViewSet, basename='api-licence')

from rest_framework.routers import DefaultRouter

from .viewsets import (AuthorViewSet, LicenceViewSet, SourceViewSet)

router = DefaultRouter()
router.register('authors', AuthorViewSet, basename='api-author')
router.register('licences', LicenceViewSet, basename='api-licence')
router.register('sources', SourceViewSet, basename='api-source')

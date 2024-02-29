from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .viewsets import LocationViewSet

router = DefaultRouter()
router.register(r'location', LocationViewSet, basename='api-location')
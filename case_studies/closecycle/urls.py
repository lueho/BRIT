from django.urls import path, include

from .router import router
from .views import (ShowcaseListView, ShowcaseCreateView, ShowcaseDetailView, ShowcaseUpdateView,
                    ShowcaseModalDeleteView, ShowcaseMapView)


urlpatterns = [
    path('showcases/', ShowcaseListView.as_view(), name='showcase-list'),
    path('showcases/map/', ShowcaseMapView.as_view(), name='Showcase'),
    path('showcases/create/', ShowcaseCreateView.as_view(), name='showcase-create'),
    path('showcases/<int:pk>/', ShowcaseDetailView.as_view(), name='showcase-detail'),
    path('showcases/<int:pk>/update/', ShowcaseUpdateView.as_view(), name='showcase-update'),
    path('showcases/<int:pk>/delete/modal/', ShowcaseModalDeleteView.as_view(), name='showcase-delete-modal'),
    path('api/', include(router.urls)),
]

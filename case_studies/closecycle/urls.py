from django.urls import include, path

from .router import router
from .views import (ShowcaseCreateView, ShowcaseDetailView, ShowcaseMapView, ShowcaseModalDeleteView,
                    ShowcasePrivateFilterView, ShowcasePublishedListView, ShowcaseUpdateView)

urlpatterns = [
    path('showcases/', ShowcasePublishedListView.as_view(), name='showcase-list'),
    path('showcases/user/', ShowcasePrivateFilterView.as_view(), name='showcase-list-owned'),
    path('showcases/map/', ShowcaseMapView.as_view(), name='Showcase'),
    path('showcases/create/', ShowcaseCreateView.as_view(), name='showcase-create'),
    path('showcases/<int:pk>/', ShowcaseDetailView.as_view(), name='showcase-detail'),
    path('showcases/<int:pk>/update/', ShowcaseUpdateView.as_view(), name='showcase-update'),
    path('showcases/<int:pk>/delete/modal/', ShowcaseModalDeleteView.as_view(), name='showcase-delete-modal'),
    path('api/', include(router.urls)),
]

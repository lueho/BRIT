from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import path, include
from django.views.generic import RedirectView

from .views import HomeView, ContributorsView

admin.autodiscover()
admin.site.enable_nav_sidebar = False

urlpatterns = [
    path('', RedirectView.as_view(url='/home'), name='entry'),
    path('favicon.ico', RedirectView.as_view(url=staticfiles_storage.url("favicon.ico")), ),
    path('home/', HomeView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('contributors/', ContributorsView.as_view(), name='contributors'),
    path('maps/', include('maps.urls')),
    path('material_manager/', include('material_manager.urls')),
    path('scenario_builder/', include('scenario_builder.urls')),
    path('scenario_evaluator/', include('scenario_evaluator.urls')),
    path('case_studies/nantes/', include('case_studies.flexibi_nantes.urls')),
    path('library/', include('library.urls')),
    path('cookies/', include('cookie_consent.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

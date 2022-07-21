import debug_toolbar
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from .views import HomeView, ContributorsView, PrivacyPolicyView

from rest_framework.authtoken.views import obtain_auth_token

admin.autodiscover()
admin.site.enable_nav_sidebar = False

urlpatterns = [
    path('', RedirectView.as_view(url='/home'), name='entry'),
    path('__debug__/', include(debug_toolbar.urls)),
    path('home/', HomeView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('contributors/', ContributorsView.as_view(), name='contributors'),
    path('maps/', include('maps.urls')),
    path('materials/', include('materials.urls')),
    path('sources/', include('sources.urls')),
    path('inventories/', include('inventories.urls')),
    path('interfaces/simucf/', include('interfaces.simucf.urls')),
    path('case_studies/nantes/', include('case_studies.flexibi_nantes.urls')),
    path('waste_collection/', include('case_studies.soilcom.urls')),
    path('bibliography/', include('bibliography.urls')),
    path('cookies/', include('cookie_consent.urls')),
    path('privacy_policy/', PrivacyPolicyView.as_view(), name='privacypolicy'),
    path('api-token-auth/', obtain_auth_token, name='api-token-auth'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

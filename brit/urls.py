import debug_toolbar
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.views.generic import RedirectView, TemplateView
from rest_framework.authtoken.views import obtain_auth_token

from utils.views import DynamicRedirectView
from .sitemaps import DynamicViewSitemap, HomepageSitemap
from .views import HomeView, AboutView, LearningView, PrivacyPolicyView

admin.autodiscover()
admin.site.enable_nav_sidebar = False

sitemaps = {
    'homepage': HomepageSitemap,
    'dynamic': DynamicViewSitemap,
}

urlpatterns = [
    path('', RedirectView.as_view(url='/home'), name='entry'),
    path('__debug__/', include(debug_toolbar.urls)),
    path('utils/', include('utils.urls')),
    path('home/', HomeView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('about/', AboutView.as_view(), name='about'),
    path('learning/', LearningView.as_view(), name='learning'),
    path('distributions/', include('distributions.urls')),
    path('maps/', include('maps.urls')),
    path('materials/', include('materials.urls')),
    path('sources/', include('sources.urls')),
    path('inventories/', include('inventories.urls')),
    path('interfaces/simucf/', include('interfaces.simucf.urls')),
    path('case_studies/hamburg/', include('case_studies.flexibi_hamburg.urls')),
    path('case_studies/nantes/', include('case_studies.flexibi_nantes.urls')),
    path('waste_collection/', include('case_studies.soilcom.urls')),
    path('closecycle/', include('case_studies.closecycle.urls')),
    path('bibliography/', include('bibliography.urls')),
    path('cookies/', include('cookie_consent.urls')),
    path('privacy_policy/', PrivacyPolicyView.as_view(), name='privacypolicy'),
    path('api-token-auth/', obtain_auth_token, name='api-token-auth'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path('<str:short_code>/', DynamicRedirectView.as_view(), name='redirect'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

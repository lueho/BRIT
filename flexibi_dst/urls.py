from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

from .views import HomeView

urlpatterns = [
    path('', RedirectView.as_view(url='/home'), name='entry'),
    path('home/', HomeView.as_view(), name='home'),
    path('admin/', admin.site.urls),
    path('users/', include('users.urls')),
    path('bioresource_explorer/', include('bioresource_explorer.urls')),
    path('material_manager/', include('material_manager.urls')),
    path('scenario_builder/', include('scenario_builder.urls')),
    path('scenario_evaluator/', include('scenario_evaluator.urls')),
    path('library/', include('library.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)

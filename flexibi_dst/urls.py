from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path, include

from . import views
from .views import DstLoginView, ScriptTestView

urlpatterns = [
    path('', views.dst, name='home'),
    path('admin/', admin.site.urls),
    path('login/', DstLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), {'next_page': settings.LOGOUT_REDIRECT_URL}, name='logout'),
    path('bioresource_explorer/', include('bioresource_explorer.urls')),
    path('scenario_builder/', include('scenario_builder.urls')),
    path('scenario_evaluator/', include('scenario_evaluator.urls')),
    path('script_test/', ScriptTestView.as_view(), name='script_test')
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)

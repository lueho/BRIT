from django.urls import include, path

from .views import UserProfileView, UserDeleteView, ModalLoginRequiredMessage

urlpatterns = [
    path('', include('registration.backends.default.urls')),
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('loginrequired/', ModalLoginRequiredMessage.as_view(), name='loginrequiredmessage'),
    path('<int:pk>/delete/', UserDeleteView.as_view(), name='user_delete')
]

from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from .views import UserProfileView, UserDeleteView, UserRegistrationView, ModalLoginView, ModalLoginRequiredMessage

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('login/', ModalLoginView.as_view(), name='login'),
    path('loginrequired/', ModalLoginRequiredMessage.as_view(), name='loginrequiredmessage'),
    path('logout/', LogoutView.as_view(template_name='logout.html'), name='logout'),
    path('<int:pk>/delete/', UserDeleteView.as_view(), name='user_delete')
]

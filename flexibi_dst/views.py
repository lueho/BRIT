from django.conf import settings
from django.contrib.auth.models import User
from django.views.generic import TemplateView, ListView


class HomeView(TemplateView):
    template_name = 'home.html'


class DualUserListView(ListView):
    standard_owner = User.objects.get(username=settings.PUBLIC_OBJECT_OWNER)
    model = None
    object_list = None

    def get(self, request, *args, **kwargs):
        standard_objects = self.model.objects.filter(owner=8)
        if request.user.is_authenticated:
            user_objects = self.model.objects.filter(owner=self.request.user)
        else:
            user_objects = self.model.objects.none()
        context = {
            'standard_objects': standard_objects,
            'user_objects': user_objects
        }
        return self.render_to_response(context)

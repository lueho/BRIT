from django.contrib.auth.models import User
from django.views.generic import TemplateView, ListView


class HomeView(TemplateView):
    template_name = 'home.html'


class DualUserListView(ListView):
    standard_owner = User.objects.get(username='flexibi')

    def get(self, request, *args, **kwargs):
        standard_objects = self.model.objects.filter(owner=self.standard_owner)
        if request.user.is_authenticated:
            user_objects = self.model.objects.filter(owner=self.request.user)
        else:
            user_objects = self.model.objects.none()
        context = {
            'standard_objects': standard_objects,
            'user_objects': user_objects
        }
        return self.render_to_response(context)

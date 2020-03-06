from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.contrib.auth.forms import AuthenticationForm

def dst(request):
    return render(request, 'map.html')
    
def home(request):
    return render(request, 'base.html', {})
    
class DstLoginView(LoginView):
 template_name = 'login.html'
 form_class = AuthenticationForm
from django.shortcuts import render

def dst(request):
    return render(request, 'map.html')
    
def home(request):
    return render(request, 'base.html', {})
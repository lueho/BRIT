from django.shortcuts import render

def dst(request):
    return render(request, 'map.html')
from django.contrib import admin

from .models import Author, Source, Licence


admin.site.register(Author)
admin.site.register(Licence)
admin.site.register(Source)

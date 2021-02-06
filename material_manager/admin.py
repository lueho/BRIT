from django.contrib import admin
from django.contrib.admin import ModelAdmin

from .models import (Material,
                     MaterialComponent,
                     MaterialComponentShare,
                     MaterialComponentGroup,
                     )


@admin.register(Material)
class MaterialAdmin(ModelAdmin):
    list_display = ('name', 'stan_flow_id', 'is_feedstock', 'description',)


@admin.register(MaterialComponentGroup)
class MaterialComponentGroupAdmin(ModelAdmin):
    list_display = ('name', 'description',)


admin.site.register(MaterialComponent)
admin.site.register(MaterialComponentShare)

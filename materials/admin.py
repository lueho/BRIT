from django.contrib import admin
from django.contrib.admin import ModelAdmin

from .models import (Material,
                     MaterialSettings,
                     MaterialComponent,
                     MaterialComponentShare,
                     MaterialComponentGroup,
                     MaterialComponentGroupSettings,
                     CompositionSet
                     )


@admin.register(Material)
class MaterialAdmin(ModelAdmin):
    list_display = ('name', 'stan_flow_id', 'is_feedstock', 'description',)


admin.site.register(MaterialSettings)


@admin.register(MaterialComponentGroup)
class MaterialComponentGroupAdmin(ModelAdmin):
    list_display = ('name', 'description',)


admin.site.register(CompositionSet)
admin.site.register(MaterialComponent)
admin.site.register(MaterialComponentShare)
admin.site.register(MaterialComponentGroupSettings)

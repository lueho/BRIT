from django_tomselect.app_settings import PluginClearButton
from django_tomselect.forms import TomSelectConfig, TomSelectModelChoiceField

from utils.forms import SimpleModelForm

from .models import Showcase


class ShowcaseModelForm(SimpleModelForm):
    region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
            placeholder="------",
            highlight=True,
            label_field="name",
            open_on_focus=True,
            plugin_clear_button=PluginClearButton(
                title="Clear Selection", class_name="clear-button"
            ),
        ),
        label="Region",
    )

    class Meta:
        model = Showcase
        fields = ("name", "region", "description")

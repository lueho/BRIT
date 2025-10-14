from django_tomselect.forms import TomSelectConfig, TomSelectModelChoiceField

from utils.forms import SimpleModelForm

from .models import Showcase


class ShowcaseModelForm(SimpleModelForm):
    region = TomSelectModelChoiceField(
        config=TomSelectConfig(
            url="region-autocomplete",
            label_field="name",
        ),
        label="Region",
    )

    class Meta:
        model = Showcase
        fields = ("name", "region", "description")

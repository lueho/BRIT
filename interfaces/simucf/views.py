from string import Template

from django.http import HttpResponse
from django.views.generic import FormView

from .forms import SimuCFModelForm
from .input_file_template import template_string
from .serializers import SimuCFSerializer, SimuCF


class SimuCFFormView(FormView):
    form_class = SimuCFModelForm
    template_name = 'simucf-form.html'

    def form_valid(self, form):
        template = Template(template_string)
        serializer = SimuCFSerializer(
            SimuCF(
                material=form.cleaned_data['input_material'],
                amount=form.cleaned_data['amount'],
                length_of_treatment=form.cleaned_data['length_of_treatment']
            )
        )
        file_content = template.substitute(**serializer.data)
        response = HttpResponse(file_content, content_type='application/text charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="simucf-input.txt"'
        return response

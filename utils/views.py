from urllib.parse import urlencode

from crispy_forms.helper import FormHelper
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import ListView, TemplateView

from .models import Redirect


class NextOrSuccessUrlMixin:
    """
    If a 'next=<url>' parameter is given in the query string of the url,
    the user will be redirected to the given url instead of the url resulting
    from the get_success_url() method.
    """

    def get_success_url(self):
        # Prefer POST 'next' (form-hidden field), fall back to GET 'next'
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        return next_url if next_url else super().get_success_url()


class NoFormTagMixin:
    """
    Mixin for generic *model form* views (CreateView, UpdateView, etc.)
    that asks crispy‑forms **not** to emit a surrounding <form> … </form>.

    • Set ``form_tag = True`` in a subclass if a particular view *does*
      need the tag back.
    """

    form_tag = False  # default for every view that uses the mixin

    def get_form(self, form_class=None):
        form = super().get_form(form_class)

        if self.form_tag is False:
            helper = getattr(form, "helper", FormHelper())
            helper.form_tag = False
            form.helper = helper
        return form


class ModalMessageView(TemplateView):
    template_name = "modal_message.html"
    title = "Title"
    message = "Message"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"title": self.title, "message": self.message})
        return context


class FilterDefaultsMixin:
    """
    A mixin that extends FilterView to add the query string of the default filter values to the URL of the resulting page.
    This is useful when you want to have default filters applied when the page is first loaded.
    """

    initial_values = {}
    filterset_class = None

    def get_default_filters(self):
        initial_values = {}
        for name, filter_ in self.filterset_class.base_filters.items():
            if filter_.extra.get("initial"):
                initial_values[name] = filter_.extra["initial"]
        return initial_values

    def get(self, request, *args, **kwargs):
        """
        Overrides the get method of the FilterView.
        If the request method is GET and the request's parameters are empty,
        it redirects to the same page but with the default filters as parameters.

        Args:
            request: The request that triggered this view.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            HttpResponse: The HttpResponse object.
        """
        response = super().get(request, *args, **kwargs)

        if request.method == "GET" and not request.GET:
            self.initial_values = self.get_default_filters()
            if self.initial_values:
                params = urlencode(self.initial_values)
                return HttpResponseRedirect(f"{request.path}?{params}")

        return response


class ModelSelectOptionsView(ListView):
    """
    Returns a pre-rendered list of options for a select DOM element as json response. This is useful for updating
    options when new objects have been created via ajax.
    """

    model = None
    template_name = "html_select_element_options.html"
    object_list = None
    include_empty_option = True
    selected_object = None

    def get_selected_object(self):
        """
        Returns the element, which will be selected in the new options list. By default this will be the
        newest created element. Override this if you require a different behaviour.
        """
        return self.selected_object

    def get_selected_object_pk(self):
        """
        Returns the primary key of the selected object, if there is any.
        """
        selected_object = self.get_selected_object()
        if selected_object:
            return selected_object.pk
        return None

    def get_queryset(self):
        """
        Returns a queryset of all the options that will be rendered in the template. By default returns all objects.
        Override this if you want to limit the choices.
        """
        return super().get_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "include_empty_option": self.include_empty_option,
                "selected": self.get_selected_object_pk(),
            }
        )
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        return JsonResponse(
            {
                "options": render_to_string(
                    self.template_name,
                    context=self.get_context_data(),
                    request=self.request,
                )
            }
        )


class UtilsDashboardView(TemplateView):
    template_name = "utils_dashboard.html"

    def get_context_data(self, **kwargs):
        from utils.properties.models import Property, Unit

        context = super().get_context_data(**kwargs)
        context["unit_count"] = Unit.objects.filter(
            publication_status="published"
        ).count()
        context["property_count"] = Property.objects.filter(
            publication_status="published"
        ).count()
        return context


class DynamicRedirectView(View):
    """
    A view that handles dynamic redirection based on a short code.
    If no such object exists, it returns a proper 404 response without logging an error.
    """

    def get(self, request, short_code):
        try:
            redirect_obj = Redirect.objects.get(short_code=short_code)
            return HttpResponseRedirect(
                f"{request.scheme}://{request.get_host()}{redirect_obj.full_path}"
            )
        except Redirect.DoesNotExist:
            return render(request, "404.html", status=404)

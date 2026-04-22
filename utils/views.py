from urllib.parse import urlencode

from crispy_forms.helper import FormHelper
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views import View
from django.views.generic import ListView, TemplateView

from .models import Redirect


def build_breadcrumb_context(
    *,
    parent_module_label=None,
    parent_module_url=None,
    module_label=None,
    module_url=None,
    section_label=None,
    section_url=None,
    object_label=None,
    object_url=None,
    action_label=None,
    page_title=None,
):
    return {
        key: value
        for key, value in {
            "breadcrumb_parent_module_label": parent_module_label,
            "breadcrumb_parent_module_url": parent_module_url,
            "breadcrumb_module_label": module_label,
            "breadcrumb_module_url": module_url,
            "breadcrumb_section_label": section_label,
            "breadcrumb_section_url": section_url,
            "breadcrumb_object_label": object_label,
            "breadcrumb_object_url": object_url,
            "breadcrumb_action_label": action_label,
            "breadcrumb_page_title": page_title,
        }.items()
        if value is not None
    }


class BreadcrumbContextMixin:
    breadcrumb_parent_module_label = None
    breadcrumb_parent_module_url = None
    breadcrumb_module_label = None
    breadcrumb_module_url = None
    breadcrumb_section_label = None
    breadcrumb_section_url = None
    breadcrumb_object_label = None
    breadcrumb_object_url = None
    breadcrumb_action_label = None
    breadcrumb_page_title = None

    def get_breadcrumb_parent_module_label(self):
        return self.breadcrumb_parent_module_label

    def get_breadcrumb_parent_module_url(self):
        return self.breadcrumb_parent_module_url

    def get_breadcrumb_module_label(self):
        return self.breadcrumb_module_label

    def get_breadcrumb_module_url(self):
        return self.breadcrumb_module_url

    def get_breadcrumb_section_label(self):
        return self.breadcrumb_section_label

    def get_breadcrumb_section_url(self):
        return self.breadcrumb_section_url

    def get_breadcrumb_object_label(self):
        return self.breadcrumb_object_label

    def get_breadcrumb_object_url(self):
        return self.breadcrumb_object_url

    def get_breadcrumb_action_label(self):
        return self.breadcrumb_action_label

    def get_breadcrumb_page_title(self):
        return self.breadcrumb_page_title

    def get_breadcrumb_context(self):
        return build_breadcrumb_context(
            parent_module_label=self.get_breadcrumb_parent_module_label(),
            parent_module_url=self.get_breadcrumb_parent_module_url(),
            module_label=self.get_breadcrumb_module_label(),
            module_url=self.get_breadcrumb_module_url(),
            section_label=self.get_breadcrumb_section_label(),
            section_url=self.get_breadcrumb_section_url(),
            object_label=self.get_breadcrumb_object_label(),
            object_url=self.get_breadcrumb_object_url(),
            action_label=self.get_breadcrumb_action_label(),
            page_title=self.get_breadcrumb_page_title(),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_breadcrumb_context())
        return context


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
        context.update({
            "include_empty_option": self.include_empty_option,
            "selected": self.get_selected_object_pk(),
        })
        return context

    def get(self, request, *args, **kwargs):
        self.object_list = self.get_queryset()
        return JsonResponse({
            "options": render_to_string(
                self.template_name,
                context=self.get_context_data(),
                request=self.request,
            )
        })


class UtilsDashboardView(BreadcrumbContextMixin, TemplateView):
    template_name = "utils_dashboard.html"
    breadcrumb_module_label = "Utilities"
    breadcrumb_page_title = "Utilities"


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

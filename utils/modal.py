from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LoginView
from django.http import HttpResponse, HttpResponseRedirect
from django.views import generic


def is_ajax(request):
    if request is None:
        return False
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


class PassRequestMixin:
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs


class PopRequestMixin:
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)


class CreateUpdateAjaxMixin:
    def save(self, commit=True):
        request = getattr(self, "request", None)
        is_ajax_request = is_ajax(request)
        async_update = bool(request and request.POST.get("asyncUpdate") == "True")

        if not is_ajax_request or async_update:
            return super().save(commit=commit)

        return super().save(commit=False)


class DeleteMessageMixin:
    def post(self, request, *args, **kwargs):
        if is_ajax(request):
            self.object = self.get_object()
            return HttpResponseRedirect(self.get_success_url())

        messages.success(request, self.success_message)
        return super().post(request, *args, **kwargs)


class LoginAjaxMixin:
    def form_valid(self, form):
        if not is_ajax(self.request):
            auth_login(self.request, form.get_user())
            messages.success(self.request, self.success_message)
        return HttpResponseRedirect(self.get_success_url())


class FormValidationMixin:
    def get_success_message(self):
        if hasattr(self, "success_message"):
            return self.success_message
        return None

    def get_success_url(self):
        if self.success_url:
            return self.success_url
        return super().get_success_url()

    def form_valid(self, form):
        is_ajax_request = is_ajax(self.request)
        async_update = self.request.POST.get("asyncUpdate") == "True"

        if is_ajax_request:
            if async_update:
                self.object = form.save()
            return HttpResponse(status=204)

        self.object = form.save()
        success_message = self.get_success_message()
        if success_message:
            messages.success(self.request, success_message)
        return HttpResponseRedirect(self.get_success_url())


class BSModalLoginView(LoginAjaxMixin, LoginView):
    pass


class BSModalFormView(PassRequestMixin, generic.FormView):
    pass


class BSModalCreateView(PassRequestMixin, FormValidationMixin, generic.CreateView):
    pass


class BSModalUpdateView(PassRequestMixin, FormValidationMixin, generic.UpdateView):
    pass


class BSModalReadView(generic.DetailView):
    pass


class BSModalDeleteView(DeleteMessageMixin, generic.DeleteView):
    pass

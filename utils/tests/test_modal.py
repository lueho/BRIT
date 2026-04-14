from unittest.mock import patch

from django.forms import Form
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, TestCase

from utils.modal import (
    CreateUpdateAjaxMixin,
    DeleteMessageMixin,
    FormValidationMixin,
    LoginAjaxMixin,
    PassRequestMixin,
    PopRequestMixin,
)


class ModalMixinTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_pass_request_mixin_adds_request_to_form_kwargs(self):
        request = self.factory.get("/")

        class BaseView:
            def get_form_kwargs(self):
                return {"initial": {}}

        class TestView(PassRequestMixin, BaseView):
            def __init__(self, request):
                self.request = request

        view = TestView(request)

        self.assertEqual(view.get_form_kwargs()["initial"], {})
        self.assertIs(view.get_form_kwargs()["request"], request)

    def test_pop_request_mixin_attaches_request_to_form(self):
        request = self.factory.get("/")

        class TestForm(PopRequestMixin, Form):
            pass

        form = TestForm(request=request)

        self.assertIs(form.request, request)

    def test_create_update_ajax_mixin_uses_commit_false_for_ajax_preflight(self):
        request = self.factory.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        class SaveRecorder:
            def __init__(self):
                self.calls = []

            def save(self, commit=True):
                self.calls.append(commit)
                return commit

        class TestForm(CreateUpdateAjaxMixin, SaveRecorder):
            pass

        form = TestForm()
        form.request = request

        result = form.save()

        self.assertFalse(result)
        self.assertEqual(form.calls, [False])

    def test_create_update_ajax_mixin_saves_on_async_update(self):
        request = self.factory.post(
            "/",
            {"asyncUpdate": "True"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        class SaveRecorder:
            def __init__(self):
                self.calls = []

            def save(self, commit=True):
                self.calls.append(commit)
                return commit

        class TestForm(CreateUpdateAjaxMixin, SaveRecorder):
            pass

        form = TestForm()
        form.request = request

        result = form.save()

        self.assertTrue(result)
        self.assertEqual(form.calls, [True])

    def test_form_validation_mixin_returns_204_without_saving_on_ajax_preflight(self):
        request = self.factory.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        class FakeForm:
            def __init__(self):
                self.save_calls = 0

            def save(self):
                self.save_calls += 1
                return object()

        class TestView(FormValidationMixin):
            success_url = "/done/"

            def __init__(self, request):
                self.request = request
                self.object = None

        form = FakeForm()
        view = TestView(request)

        response = view.form_valid(form)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(form.save_calls, 0)
        self.assertIsNone(view.object)

    def test_form_validation_mixin_saves_on_async_update(self):
        request = self.factory.post(
            "/",
            {"asyncUpdate": "True"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        saved_object = object()

        class FakeForm:
            def __init__(self):
                self.save_calls = 0

            def save(self):
                self.save_calls += 1
                return saved_object

        class TestView(FormValidationMixin):
            success_url = "/done/"

            def __init__(self, request):
                self.request = request
                self.object = None

        form = FakeForm()
        view = TestView(request)

        response = view.form_valid(form)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(form.save_calls, 1)
        self.assertIs(view.object, saved_object)

    def test_form_validation_mixin_redirects_and_saves_on_non_ajax_submit(self):
        request = self.factory.post("/")

        saved_object = object()

        class FakeForm:
            def __init__(self):
                self.save_calls = 0

            def save(self):
                self.save_calls += 1
                return saved_object

        class TestView(FormValidationMixin):
            success_url = "/done/"
            success_message = "Saved"

            def __init__(self, request):
                self.request = request
                self.object = None

        form = FakeForm()
        view = TestView(request)

        with patch("utils.modal.messages.success") as mock_success:
            response = view.form_valid(form)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/done/")
        self.assertEqual(form.save_calls, 1)
        self.assertIs(view.object, saved_object)
        mock_success.assert_called_once_with(request, "Saved")

    def test_delete_message_mixin_returns_redirect_without_deleting_on_ajax_preflight(
        self,
    ):
        request = self.factory.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        class BaseDeleteView:
            def __init__(self):
                self.super_called = False
                self.object = None

            def get_object(self):
                return "object"

            def get_success_url(self):
                return "/done/"

            def post(self, request, *args, **kwargs):
                self.super_called = True
                return HttpResponse("deleted")

        class TestView(DeleteMessageMixin, BaseDeleteView):
            success_message = "Deleted"

        view = TestView()

        response = view.post(request)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/done/")
        self.assertEqual(view.object, "object")
        self.assertFalse(view.super_called)

    def test_login_ajax_mixin_skips_auth_login_for_ajax_preflight(self):
        request = self.factory.post("/", HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        class FakeForm:
            def get_user(self):
                return object()

        class TestView(LoginAjaxMixin):
            success_message = "Logged in"

            def __init__(self, request):
                self.request = request

            def get_success_url(self):
                return "/done/"

        view = TestView(request)

        with patch("utils.modal.auth_login") as mock_login:
            with patch("utils.modal.messages.success") as mock_success:
                response = view.form_valid(FakeForm())

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/done/")
        mock_login.assert_not_called()
        mock_success.assert_not_called()

    def test_login_ajax_mixin_logs_in_for_non_ajax_submit(self):
        request = self.factory.post("/")
        user = object()

        class FakeForm:
            def get_user(self):
                return user

        class TestView(LoginAjaxMixin):
            success_message = "Logged in"

            def __init__(self, request):
                self.request = request

            def get_success_url(self):
                return "/done/"

        view = TestView(request)

        with patch("utils.modal.auth_login") as mock_login:
            with patch("utils.modal.messages.success") as mock_success:
                response = view.form_valid(FakeForm())

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/done/")
        mock_login.assert_called_once_with(request, user)
        mock_success.assert_called_once_with(request, "Logged in")

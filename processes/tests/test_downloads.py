from io import BytesIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.test import TestCase
from django.urls import reverse

from ..models import Process, ProcessCategory, ProcessInfoResource


class SupportingFileDownloadTests:
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="download-owner")
        cls.other = user_model.objects.create_user(username="download-other")
        cls.editor = user_model.objects.create_user(username="download-editor")
        cls.staff = user_model.objects.create_user(
            username="download-staff", is_staff=True
        )
        cls.moderator = user_model.objects.create_user(username="download-moderator")
        cls.moderator.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="processes",
                codename__in=["can_moderate_process", "can_moderate_processcategory"],
            )
        )
        cls.process = Process.objects.create(
            name="Download process",
            owner=cls.owner,
            publication_status="published",
            supplementary_document="supporting/process report.pdf",
        )
        cls.category = ProcessCategory.objects.create(
            name="Download category",
            owner=cls.owner,
            publication_status="published",
            supplementary_document="supporting/category report.pdf",
        )
        cls.process.add_editor(cls.editor, granted_by=cls.owner)
        cls.category.add_editor(cls.editor, granted_by=cls.owner)
        cls.resource = ProcessInfoResource.objects.create(
            process=cls.process,
            title="Download resource",
            resource_type=ProcessInfoResource.ResourceType.DOCUMENT,
            document="supporting/resource report.pdf",
        )

    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        self.storage = FileSystemStorage(location=media.name)
        for model, field_name in (
            (Process, "supplementary_document"),
            (ProcessCategory, "supplementary_document"),
            (ProcessInfoResource, "document"),
        ):
            storage_patch = patch.object(
                model._meta.get_field(field_name), "storage", self.storage
            )
            storage_patch.start()
            self.addCleanup(storage_patch.stop)
        self.parent = getattr(self, self.parent_attribute)
        self.file_object = getattr(self, self.file_object_attribute)
        self.field_file = getattr(self.file_object, self.field_name)
        self.download_url = reverse(self.route_name, kwargs=self.download_kwargs())
        self.detail_url = self.parent.detail_url
        self.payload = b"%PDF-1.4\nSupporting document\x00\xff\n%%EOF"

    def download_kwargs(self):
        return {"pk": self.parent.pk}

    def assert_private_response(self, response):
        directives = {value.strip() for value in response["Cache-Control"].split(",")}
        self.assertTrue({"private", "no-store"}.issubset(directives))

    def assert_download(self, response, filename=None):
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertEqual(b"".join(response.streaming_content), self.payload)
        self.assert_private_response(response)
        if filename is None:
            filename = self.field_file.name.rsplit("/", 1)[-1]
        self.assertEqual(
            response["Content-Disposition"], f'attachment; filename="{filename}"'
        )

    def assert_unavailable(self, response, status=404):
        self.assertEqual(response.status_code, status)
        self.assertFalse(response.streaming)
        self.assertTemplateUsed(response, "processes/file_unavailable.html")
        self.assertContains(response, "File unavailable", status_code=status)
        self.assertContains(response, "Try again", status_code=status)
        self.assertContains(response, f'href="{self.download_url}"', status_code=status)
        self.assertContains(response, f'href="{self.detail_url}"', status_code=status)
        self.assertNotContains(response, " download", status_code=status)
        self.assertNotContains(response, "secret-provider-details", status_code=status)
        self.assertNotContains(response, "<Error>", status_code=status)
        self.assertNotContains(response, "X-Amz", status_code=status)
        self.assertEqual(response["Content-Type"], "text/html; charset=utf-8")
        self.assertNotIn("Content-Disposition", response)
        self.assertNotIn("Location", response)
        self.assert_private_response(response)

    def assert_access_matches_detail(self, user, publication_status, expected_status):
        self.parent.publication_status = publication_status
        self.parent.save(update_fields=["publication_status"])
        self.client.logout()
        if user is not None:
            self.client.force_login(user)
        detail_response = self.client.get(self.detail_url)
        self.assertEqual(detail_response.status_code, expected_status)
        with patch.object(
            self.storage, "open", return_value=BytesIO(self.payload)
        ) as storage_open:
            response = self.client.get(self.download_url)
            self.assertEqual(response.status_code, detail_response.status_code)
            if expected_status == 200:
                self.assert_download(response)
                storage_open.assert_called_once_with(self.field_file.name, "rb")
            else:
                storage_open.assert_not_called()
                self.assert_private_response(response)

    def test_anonymous_published_download_matches_detail(self):
        self.assert_access_matches_detail(None, "published", 200)

    def test_anonymous_private_download_matches_detail_without_storage_access(self):
        self.assert_access_matches_detail(None, "private", 302)

    def test_nonowner_private_download_matches_detail_without_storage_access(self):
        self.assert_access_matches_detail(self.other, "private", 403)

    def test_owner_can_download_private_file(self):
        self.assert_access_matches_detail(self.owner, "private", 200)

    def test_editor_can_download_private_file(self):
        self.assert_access_matches_detail(self.editor, "private", 200)

    def test_staff_can_download_private_file(self):
        self.assert_access_matches_detail(self.staff, "private", 200)

    def test_moderator_can_download_private_file(self):
        self.assert_access_matches_detail(self.moderator, "private", 200)

    def test_archived_access_matches_actual_detail_for_all_roles(self):
        for user, status in (
            (None, 302),
            (self.other, 403),
            (self.owner, 200),
            (self.editor, 200),
            (self.staff, 200),
            (self.moderator, 200),
        ):
            with self.subTest(user=user):
                self.assert_access_matches_detail(user, "archived", status)

    def test_review_and_declined_access_matches_detail(self):
        for publication_status in ("review", "declined"):
            for user, status in ((None, 302), (self.other, 403), (self.owner, 200)):
                with self.subTest(publication_status=publication_status, user=user):
                    self.assert_access_matches_detail(user, publication_status, status)

    def test_streams_bytes_from_field_specific_storage(self):
        self.storage.save(self.field_file.name, ContentFile(self.payload))
        with patch.object(
            self.storage, "open", wraps=self.storage.open
        ) as storage_open:
            with patch.object(
                self.storage, "url", side_effect=AssertionError("No public URL")
            ):
                response = self.client.get(self.download_url)
            self.assert_download(response)
            storage_open.assert_called_once_with(self.field_file.name, "rb")

    def test_missing_field_returns_friendly_404_without_opening_storage(self):
        setattr(self.file_object, self.field_name, "")
        self.file_object.save(update_fields=[self.field_name])
        with patch.object(self.storage, "open") as storage_open:
            self.assert_unavailable(self.client.get(self.download_url))
            storage_open.assert_not_called()

    def test_missing_storage_key_returns_friendly_404(self):
        self.assert_unavailable(self.client.get(self.download_url))

    def test_provider_missing_key_returns_friendly_404(self):
        for code in ("NoSuchKey", "NotFound", "404"):
            error = ClientError(
                {"Error": {"Code": code, "Message": "secret-provider-details"}},
                "GetObject",
            )
            with (
                self.subTest(code=code),
                patch.object(self.storage, "open", side_effect=error),
            ):
                self.assert_unavailable(self.client.get(self.download_url))

    def test_provider_http_404_returns_friendly_404(self):
        error = ClientError(
            {
                "Error": {"Code": "Unknown", "Message": "secret-provider-details"},
                "ResponseMetadata": {"HTTPStatusCode": 404},
            },
            "HeadObject",
        )
        with patch.object(self.storage, "open", side_effect=error):
            self.assert_unavailable(self.client.get(self.download_url))

    def test_storage_permission_and_unavailability_errors_return_friendly_503(self):
        errors = (
            PermissionError("secret-provider-details"),
            OSError("secret-provider-details"),
            NoCredentialsError(),
            EndpointConnectionError(
                endpoint_url="https://secret-provider-details.invalid"
            ),
            ClientError(
                {
                    "Error": {
                        "Code": "AccessDenied",
                        "Message": "secret-provider-details",
                    }
                },
                "GetObject",
            ),
            ClientError(
                {"Error": {"Code": "SlowDown", "Message": "secret-provider-details"}},
                "GetObject",
            ),
        )
        for error in errors:
            with (
                self.subTest(error=type(error).__name__),
                patch.object(self.storage, "open", side_effect=error),
            ):
                self.assert_unavailable(self.client.get(self.download_url), status=503)

    def test_lazy_read_failures_are_handled_before_response_and_stream_is_closed(self):
        for error, status in (
            (FileNotFoundError("secret-provider-details"), 404),
            (
                ClientError(
                    {
                        "Error": {
                            "Code": "AccessDenied",
                            "Message": "secret-provider-details",
                        }
                    },
                    "GetObject",
                ),
                503,
            ),
            (OSError("secret-provider-details"), 503),
        ):
            stream = BytesIO(self.payload)
            with (
                self.subTest(error=type(error).__name__),
                patch.object(self.storage, "open", return_value=stream),
                patch.object(stream, "read", side_effect=error),
            ):
                self.assert_unavailable(
                    self.client.get(self.download_url), status=status
                )
                self.assertTrue(stream.closed)

    def test_lazy_seek_failure_is_handled_before_response_and_stream_is_closed(self):
        stream = BytesIO(self.payload)
        with (
            patch.object(self.storage, "open", return_value=stream),
            patch.object(
                stream, "seek", side_effect=OSError("secret-provider-details")
            ),
        ):
            self.assert_unavailable(self.client.get(self.download_url), status=503)
            self.assertTrue(stream.closed)

    def test_initial_probe_is_bounded_and_stream_is_rewound(self):
        stream = BytesIO(self.payload)
        with (
            patch.object(self.storage, "open", return_value=stream),
            patch.object(stream, "read", wraps=stream.read) as read,
        ):
            response = self.client.get(self.download_url)
            read.assert_called_once_with(1)
            self.assertFalse(stream.closed)
            self.assertEqual(stream.tell(), 0)
            self.assert_download(response)
            self.assertTrue(stream.closed)

    def test_attachment_filename_excludes_paths_and_control_characters(self):
        setattr(
            self.file_object, self.field_name, "private/folder\\original\r\n report.pdf"
        )
        self.file_object.save(update_fields=[self.field_name])
        with patch.object(self.storage, "open", return_value=BytesIO(self.payload)):
            response = self.client.get(self.download_url)
        self.assert_download(response, filename="original report.pdf")

    def test_unexpected_programming_errors_are_not_hidden(self):
        with patch.object(
            self.storage, "open", side_effect=ValueError("programming failure")
        ):
            with self.assertRaisesMessage(ValueError, "programming failure"):
                self.client.get(self.download_url)

    def test_model_download_property_reverses_protected_route(self):
        with patch.object(
            self.storage, "url", side_effect=AssertionError("No public URL")
        ):
            self.assertEqual(
                getattr(self.file_object, self.url_property), self.download_url
            )

    def test_missing_parent_does_not_open_storage(self):
        kwargs = self.download_kwargs()
        kwargs["pk"] += 1000000
        with patch.object(self.storage, "open") as storage_open:
            response = self.client.get(reverse(self.route_name, kwargs=kwargs))
            self.assertEqual(response.status_code, 404)
            self.assert_private_response(response)
            storage_open.assert_not_called()


class ProcessSupplementaryDocumentDownloadTests(SupportingFileDownloadTests, TestCase):
    parent_attribute = "process"
    file_object_attribute = "process"
    field_name = "supplementary_document"
    url_property = "supplementary_document_download_url"
    route_name = "processes:process-supplementary-document"


class ProcessCategorySupplementaryDocumentDownloadTests(
    SupportingFileDownloadTests, TestCase
):
    parent_attribute = "category"
    file_object_attribute = "category"
    field_name = "supplementary_document"
    url_property = "supplementary_document_download_url"
    route_name = "processes:processcategory-supplementary-document"


class ProcessInfoResourceDocumentDownloadTests(SupportingFileDownloadTests, TestCase):
    parent_attribute = "process"
    file_object_attribute = "resource"
    field_name = "document"
    url_property = "document_download_url"
    route_name = "processes:process-info-resource-document"

    def download_kwargs(self):
        return {"pk": self.parent.pk, "resource_pk": self.resource.pk}

    def test_resource_belongs_to_another_process(self):
        other_process = Process.objects.create(
            name="Another process", owner=self.other, publication_status="private"
        )
        self.resource.process = other_process
        self.resource.save(update_fields=["process"])
        with patch.object(self.storage, "open") as storage_open:
            self.assert_unavailable(self.client.get(self.download_url))
            storage_open.assert_not_called()

    def test_missing_resource_returns_friendly_404(self):
        self.resource.delete()
        with patch.object(self.storage, "open") as storage_open:
            self.assert_unavailable(self.client.get(self.download_url))
            storage_open.assert_not_called()

    def test_non_document_resource_is_not_downloaded(self):
        self.resource.resource_type = ProcessInfoResource.ResourceType.EXTERNAL
        self.resource.url = "https://example.com/reference"
        self.resource.save(update_fields=["resource_type", "url"])
        with patch.object(self.storage, "open") as storage_open:
            self.assert_unavailable(self.client.get(self.download_url))
            storage_open.assert_not_called()

    def test_document_target_url_is_protected_without_storage_url_lookup(self):
        with patch.object(
            self.storage, "url", side_effect=AssertionError("No public URL")
        ):
            self.assertEqual(self.resource.target_url, self.download_url)

    def test_document_target_url_remains_protected_when_field_is_missing(self):
        self.resource.document = ""
        self.assertEqual(self.resource.target_url, self.download_url)

    def test_external_and_internal_targets_are_unchanged(self):
        for resource_type, url in (
            (ProcessInfoResource.ResourceType.EXTERNAL, "https://example.com/resource"),
            (ProcessInfoResource.ResourceType.INTERNAL, "/processes/list/"),
        ):
            with self.subTest(resource_type=resource_type):
                self.resource.resource_type = resource_type
                self.resource.url = url
                self.assertEqual(self.resource.target_url, url)

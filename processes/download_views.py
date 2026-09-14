from contextlib import suppress
from ntpath import basename

from botocore.exceptions import BotoCoreError, ClientError
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.utils.cache import patch_cache_control

from utils.object_management.views import UserCreatedObjectDetailView

from .models import Process, ProcessCategory, ProcessInfoResource


class SupportingFileDownloadView(UserCreatedObjectDetailView):
    def dispatch(self, request, *args, **kwargs):
        try:
            response = super().dispatch(request, *args, **kwargs)
        except PermissionDenied:
            response = render(request, "403.html", status=403)
        except Http404:
            response = render(request, "404.html", status=404)
        patch_cache_control(response, private=True, no_store=True)
        return response

    def get_field_file(self):
        return self.object.supplementary_document

    def file_unavailable(self, status):
        return render(
            self.request,
            "processes/file_unavailable.html",
            {
                "back_url": self.object.detail_url,
                "back_label": f"Back to {self.object._meta.verbose_name}",
                "retry_url": self.request.path,
            },
            status=status,
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        stream = None
        try:
            field_file = self.get_field_file()
            if not field_file:
                return self.file_unavailable(404)
            stream = field_file.storage.open(field_file.name, "rb")
            stream.read(1)
            stream.seek(0)
            filename = (
                "".join(
                    character
                    for character in basename(field_file.name)
                    if character.isprintable()
                )
                or "document"
            )
            response = FileResponse(stream, as_attachment=True, filename=filename)
            stream = None
            return response
        except (Http404, FileNotFoundError):
            return self.file_unavailable(404)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code")
            http_status = error.response.get("ResponseMetadata", {}).get(
                "HTTPStatusCode"
            )
            status = (
                404
                if code in {"NoSuchKey", "NotFound", "404"} or http_status == 404
                else 503
            )
            return self.file_unavailable(status)
        except (OSError, BotoCoreError):
            return self.file_unavailable(503)
        finally:
            if stream is not None:
                with suppress(OSError, BotoCoreError, ClientError):
                    stream.close()


class ProcessSupplementaryDocumentDownloadView(SupportingFileDownloadView):
    model = Process


class ProcessCategorySupplementaryDocumentDownloadView(SupportingFileDownloadView):
    model = ProcessCategory


class ProcessInfoResourceDocumentDownloadView(SupportingFileDownloadView):
    model = Process

    def get_field_file(self):
        resource = get_object_or_404(
            self.object.info_resources,
            pk=self.kwargs["resource_pk"],
            resource_type=ProcessInfoResource.ResourceType.DOCUMENT,
        )
        return resource.document

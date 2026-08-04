"""API views for the versioned, provider-neutral NUTS vintage import contract."""

from dataclasses import asdict

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .contracts import NUTS_IMPORT_SCHEMA
from .importers import import_nuts_payload
from .permissions import CanImportNutsRegions
from .serializers import NutsImportSerializer


def _truthy(value):
    return str(value).lower() in ("1", "true", "yes", "on")


class NutsImportView(APIView):
    """Bulk-import one NUTS vintage through the public v1.0 contract.

    ``POST`` a payload validated against :data:`NUTS_IMPORT_SCHEMA`, lowest
    level first. Pass ``?dry_run=true`` (or ``"dry_run": true``) to receive a
    report without persisting anything.
    """

    permission_classes = (CanImportNutsRegions,)

    def post(self, request):
        serializer = NutsImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dry_run = _truthy(request.query_params.get("dry_run", ""))
        report = import_nuts_payload(
            serializer.validated_data, user=request.user, dry_run=dry_run
        )

        if report.errors:
            response_status = status.HTTP_400_BAD_REQUEST
        elif report.committed and report.created:
            response_status = status.HTTP_201_CREATED
        else:
            response_status = status.HTTP_200_OK
        return Response(asdict(report), status=response_status)


class NutsImportSchemaView(APIView):
    """Serve the JSON Schema for the NUTS vintage import payload contract."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        return Response(NUTS_IMPORT_SCHEMA)

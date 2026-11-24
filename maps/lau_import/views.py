"""API views for the versioned, provider-neutral LAU vintage import contract."""

from dataclasses import asdict

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from maps.import_common import ImportJSONParser, _truthy

from .contracts import LAU_IMPORT_SCHEMA
from .importers import import_lau_payload
from .permissions import CanImportLauRegions
from .serializers import LauImportSerializer


class LauImportView(APIView):
    """Bulk-import one LAU year through the public v1.0 contract.

    ``POST`` a payload validated against :data:`LAU_IMPORT_SCHEMA`. A payload
    is one batch of a year; rows absent from it are left untouched. Pass
    ``?dry_run=true`` (or ``"dry_run": true``) to receive a report without
    persisting anything.
    """

    permission_classes = (CanImportLauRegions,)
    parser_classes = (ImportJSONParser,)

    def post(self, request):
        serializer = LauImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dry_run = _truthy(request.query_params.get("dry_run", ""))
        report = import_lau_payload(
            serializer.validated_data, user=request.user, dry_run=dry_run
        )

        if report.errors:
            response_status = status.HTTP_400_BAD_REQUEST
        elif report.committed and report.created:
            response_status = status.HTTP_201_CREATED
        else:
            response_status = status.HTTP_200_OK
        return Response(asdict(report), status=response_status)


class LauImportSchemaView(APIView):
    """Serve the JSON Schema for the LAU vintage import payload contract."""

    authentication_classes = ()
    permission_classes = (AllowAny,)
    policy_exempt = "Static import JSON schema; serves no record data"

    def get(self, request):
        return Response(LAU_IMPORT_SCHEMA)

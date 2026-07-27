"""API views for the versioned, provider-neutral population import contract."""

from dataclasses import asdict

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .contracts import POPULATION_IMPORT_SCHEMA
from .importers import import_population_payload
from .permissions import CanImportPopulation
from .serializers import PopulationImportSerializer


def _truthy(value):
    return str(value).lower() in ("1", "true", "yes", "on")


class PopulationImportView(APIView):
    """Bulk-import population observations through the public v1.0 contract.

    ``POST`` a payload validated against :data:`POPULATION_IMPORT_SCHEMA`.
    Pass ``?dry_run=true`` (or ``"dry_run": true`` in the body) to validate and
    receive an import report without persisting anything.
    """

    permission_classes = (CanImportPopulation,)

    def post(self, request):
        serializer = PopulationImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        dry_run = _truthy(request.query_params.get("dry_run", ""))
        report = import_population_payload(
            serializer.validated_data, user=request.user, dry_run=dry_run
        )

        response_status = (
            status.HTTP_201_CREATED
            if report.committed and report.created
            else status.HTTP_200_OK
        )
        return Response(asdict(report), status=response_status)


class PopulationImportSchemaView(APIView):
    """Serve the JSON Schema for the population import payload contract."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def get(self, request):
        return Response(POPULATION_IMPORT_SCHEMA)

from django.urls import path

from .views import NutsImportSchemaView, NutsImportView

app_name = "nuts"

urlpatterns = [
    path("api/import/", NutsImportView.as_view(), name="import"),
    path("api/import/schema/", NutsImportSchemaView.as_view(), name="import-schema"),
]

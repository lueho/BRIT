from django.urls import path

from .views import PopulationImportSchemaView, PopulationImportView

app_name = "population"

urlpatterns = [
    path("api/import/", PopulationImportView.as_view(), name="import"),
    path(
        "api/import/schema/",
        PopulationImportSchemaView.as_view(),
        name="import-schema",
    ),
]

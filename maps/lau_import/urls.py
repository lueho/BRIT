from django.urls import path

from .views import LauImportSchemaView, LauImportView

app_name = "lau"

urlpatterns = [
    path("api/import/", LauImportView.as_view(), name="import"),
    path("api/import/schema/", LauImportSchemaView.as_view(), name="import-schema"),
]

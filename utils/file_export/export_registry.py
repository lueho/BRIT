# Registry for exportable UserCreatedObject-derived models
from collections import namedtuple

from django.apps import apps

ExportSpec = namedtuple("ExportSpec", ["model", "filterset", "serializer", "renderers"])

EXPORT_REGISTRY = {}


def register_export(model_label, filterset, serializer, renderers):
    model = apps.get_model(model_label)
    EXPORT_REGISTRY[model_label] = ExportSpec(model, filterset, serializer, renderers)


def get_export_spec(model_label):
    return EXPORT_REGISTRY[model_label]

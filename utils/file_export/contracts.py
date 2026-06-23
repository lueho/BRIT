from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDomainExport:
    model_label: str
    filterset: object
    serializer: object
    renderers: dict[str, object]

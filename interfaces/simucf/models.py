from decimal import Decimal

from django.core.exceptions import ImproperlyConfigured
from django.db.models import Manager

from materials.composition_normalization import get_sample_normalized_compositions
from materials.models import (
    ComponentMeasurement,
    Composition,
    MaterialComponent,
    Sample,
)


class InputMaterialManager(Manager):
    def get_queryset(self):
        component_names = [
            "Carbohydrates",
            "Amino Acids",
            "Starches",
            "Hemicellulose",
            "Fats",
            "Waxes",
            "Proteins",
            "Cellulose",
            "Lignin",
        ]
        compatible_measurements = ComponentMeasurement.objects.filter(
            group__name="Biochemical Composition",
            component__name__in=component_names,
        ).exclude(
            component__in=MaterialComponent.objects.exclude(name__in=component_names)
        )
        return (
            super()
            .get_queryset()
            .filter(component_measurements__in=compatible_measurements)
            .distinct()
        )


class InputMaterial(Sample):
    """Proxy class to check compatibility/completeness of stored material samples for SimuCF. Also implements properties
    that are required for serialization."""

    objects = InputMaterialManager()

    class Meta:
        proxy = True

    @property
    def composition(self):
        try:
            return self.compositions.get(group__name="Biochemical Composition")
        except Composition.DoesNotExist:
            raise ImproperlyConfigured("""
            SimuCF input material needs to have a defined composition of group "Biochemical Composition"
            """) from None

    def get_normalized_component_share(self, component_name):
        composition_setting = self.composition
        for composition in get_sample_normalized_compositions(self):
            if composition.get("settings_pk") != composition_setting.pk:
                continue
            for share in composition["shares"]:
                if share["component_name"] == component_name:
                    return Decimal(str(share["average"]))
            return Decimal("0")
        return Decimal("0")

    @property
    def carbohydrates(self):
        return self.get_normalized_component_share("Carbohydrates")

    @property
    def amino_acids(self):
        return self.get_normalized_component_share("Amino Acids")

    @property
    def starch(self):
        return self.get_normalized_component_share("Starches")

    @property
    def hemicellulose(self):
        return self.get_normalized_component_share("Hemicellulose")

    @property
    def fats(self):
        return self.get_normalized_component_share("Fats")

    @property
    def waxs(self):
        return self.get_normalized_component_share("Waxes")

    @property
    def proteins(self):
        return self.get_normalized_component_share("Proteins")

    @property
    def cellulose(self):
        return self.get_normalized_component_share("Cellulose")

    @property
    def lignin(self):
        return self.get_normalized_component_share("Lignin")

    @property
    def inorganics(self):
        return 0

    @property
    def bulk_density(self):
        return 0.8

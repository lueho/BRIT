from django.core.exceptions import ImproperlyConfigured
from django.db.models import Manager

from materials.models import Composition, MaterialComponent, Sample, WeightShare


class InputMaterialManager(Manager):
    def get_queryset(self):
        component_names = [
            'Carbohydrates', 'Amino Acids', 'Starches', 'Hemicellulose', 'Fats',
            'Waxes', 'Proteins', 'Cellulose', 'Lignin'
        ]
        return super().get_queryset() \
            .filter(compositions__in=Composition.objects
                    .filter(group__name='Biochemical Composition')
                    .exclude(shares__component__in=MaterialComponent.objects.exclude(name__in=component_names))
                    .filter(shares__component__name__in=component_names))


class InputMaterial(Sample):
    """Proxy class to check compatibility/completeness of stored material samples for SimuCF. Also implements properties
    that are required for serialization."""

    objects = InputMaterialManager()

    class Meta:
        proxy = True

    @property
    def composition(self):
        try:
            return self.compositions.get(group__name='Biochemical Composition')
        except Composition.DoesNotExist:
            raise ImproperlyConfigured("""
            SimuCF input material needs to have a defined composition of group "Biochemical Composition"
            """)

    @property
    def carbohydrates(self):
        try:
            return self.composition.shares.get(component__name='Carbohydrates').average
        except WeightShare.DoesNotExist:
            return 0

    @property
    def amino_acids(self):
        try:
            return self.composition.shares.get(component__name='Amino Acids').average
        except WeightShare.DoesNotExist:
            return 0

    @property
    def starch(self):
        try:
            return self.composition.shares.get(component__name='Starches').average
        except WeightShare.DoesNotExist:
            return 0

    @property
    def hemicellulose(self):
        try:
            return self.composition.shares.get(component__name='Hemicellulose').average
        except WeightShare.DoesNotExist:
            return 0

    @property
    def fats(self):
        try:
            return self.composition.shares.get(component__name='Fats').average
        except WeightShare.DoesNotExist:
            return 0

    @property
    def waxs(self):
        try:
            return self.composition.shares.get(component__name='Waxes').average
        except WeightShare.DoesNotExist:
            return 0

    @property
    def proteins(self):
        try:
            return self.composition.shares.get(component__name='Proteins').average
        except WeightShare.DoesNotExist:
            return 0

    @property
    def cellulose(self):
        try:
            return self.composition.shares.get(component__name='Cellulose').average
        except WeightShare.DoesNotExist:
            return 0

    @property
    def lignin(self):
        try:
            return self.composition.shares.get(component__name='Lignin').average
        except WeightShare.DoesNotExist:
            return 0

    @property
    def inorganics(self):
        return 0

    @property
    def bulk_density(self):
        return 0.8

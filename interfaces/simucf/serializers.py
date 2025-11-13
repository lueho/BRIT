from rest_framework.serializers import DecimalField, Serializer, SerializerMethodField


class DecimalWithCommaField(DecimalField):
    def to_representation(self, value):
        return super().to_representation(value).replace(".", ",")


class SimuCF:
    def __init__(self, *args, **kwargs):
        self.amount = kwargs.get("amount")
        self.degr_mat_dry_solid_content = 66.6
        self.material = kwargs.get("material")
        self.carbohydrates = self.material.carbohydrates * self.amount
        self.starch = self.material.starch * self.amount
        self.amino_acids = self.material.amino_acids * self.amount
        self.hemicellulose = self.material.hemicellulose * self.amount
        self.fats = self.material.fats * self.amount
        self.waxs = self.material.waxs * self.amount
        self.proteins = self.material.proteins * self.amount
        self.cellulose = self.material.cellulose * self.amount
        self.lignin = self.material.lignin * self.amount
        self.pore_volume = 40
        self.bulk_density = 0.8
        self.settlement = 1
        self.structure_weight = 0
        self.total_solids = 50
        self.structure_density = 0.6
        self.inorganics = 0
        self.inorganics_ts = 50
        self.bulk_density = 0.8
        self.length_of_treatment = kwargs.get("length_of_treatment")
        self.evap = [0] * self.length_of_treatment
        self.water_input = [0] * self.length_of_treatment
        self.ferric_chloride = [0] * self.length_of_treatment
        self.methanol = [0] * self.length_of_treatment
        self.sulfate = [0] * self.length_of_treatment
        self.nitrate = [0] * self.length_of_treatment
        self.ammonium = [0] * self.length_of_treatment
        self.calcium_carbonate = [0] * self.length_of_treatment
        self.calcium_carbonate[0] = 2.82
        self.aeration_rate = [295] * self.length_of_treatment


class SimuCFSerializer(Serializer):
    carbohydrates = DecimalWithCommaField(max_digits=100, decimal_places=3)
    starch = DecimalWithCommaField(max_digits=100, decimal_places=3)
    amino_acids = DecimalWithCommaField(max_digits=100, decimal_places=3)
    hemicellulose = DecimalWithCommaField(max_digits=100, decimal_places=3)
    fats = DecimalWithCommaField(max_digits=100, decimal_places=3)
    waxs = DecimalWithCommaField(max_digits=100, decimal_places=3)
    proteins = DecimalWithCommaField(max_digits=100, decimal_places=3)
    degr_mat_dry_solid_content = DecimalWithCommaField(max_digits=100, decimal_places=3)
    cellulose = DecimalWithCommaField(max_digits=100, decimal_places=3)
    lignin = DecimalWithCommaField(max_digits=100, decimal_places=3)
    inorganics = DecimalWithCommaField(max_digits=100, decimal_places=3)
    bulk_density = DecimalWithCommaField(max_digits=4, decimal_places=3)
    length_of_treatment = DecimalWithCommaField(max_digits=100, decimal_places=3)
    evap = SerializerMethodField()
    water_input = SerializerMethodField()
    ferric_chloride = SerializerMethodField()
    methanol = SerializerMethodField()
    sulfate = SerializerMethodField()
    nitrate = SerializerMethodField()
    ammonium = SerializerMethodField()
    calcium_carbonate = SerializerMethodField()
    aeration_rate = SerializerMethodField()

    @staticmethod
    def format_list(value_list):
        text = ""
        for index, value in enumerate(value_list):
            value = f"{value:.3f}".replace(".", ",")
            text += f"{index},000\t{value}\n"
        return text

    def get_evap(self, obj):
        return self.format_list(obj.evap)

    def get_water_input(self, obj):
        return self.format_list(obj.water_input)

    def get_ferric_chloride(self, obj):
        return self.format_list(obj.ferric_chloride)

    def get_methanol(self, obj):
        return self.format_list(obj.methanol)

    def get_sulfate(self, obj):
        return self.format_list(obj.sulfate)

    def get_nitrate(self, obj):
        return self.format_list(obj.nitrate)

    def get_ammonium(self, obj):
        return self.format_list(obj.ammonium)

    def get_calcium_carbonate(self, obj):
        return self.format_list(obj.calcium_carbonate)

    def get_aeration_rate(self, obj):
        return self.format_list(obj.aeration_rate)

from django.contrib.postgres.fields import ArrayField


class SeasonalDistribution:

    def __init__(self, values):
        self.january = values[0]
        self.february = values[1]
        self.march = values[2]
        self.april = values[3]
        self.may = values[4]
        self.june = values[5]
        self.july = values[6]
        self.august = values[7]
        self.september = values[8]
        self.october = values[9]
        self.november = values[10]
        self.december = values[11]

    def as_dict(self):
        return {
            'January': self.january,
            'february': self.february,
            'march': self.march,
            'april': self.april,
            'may': self.may,
            'june': self.june,
            'july': self.july,
            'august': self.august,
            'september': self.september,
            'october': self.october,
            'november': self.november,
            'december': self.december
        }


class SeasonalDistributionField(ArrayField):
    description = "A seasonal distribution with a decimal number for each month of the year"

    # def __init__(self, *args, **kwargs):
    #     kwargs['size'] = 12
    #     super().__init__(self, *args, **kwargs)
    #
    # def deconstruct(self):
    #     name, path, args, kwargs = super().deconstruct()
    #     del kwargs["size"]
    #     return name, path, args, kwargs

    def db_type(self, connection):
        return 'seasonal_distribution'

    @staticmethod
    def parse_distribution(obj: SeasonalDistribution):
        return {
            'January': obj.january,
            'february': obj.february,
            'march': obj.march,
            'april': obj.april,
            'may': obj.may,
            'june': obj.june,
            'july': obj.july,
            'august': obj.august,
            'september': obj.september,
            'october': obj.october,
            'november': obj.november,
            'december': obj.december
        }

    def _from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return self.parse_distribution(value)

    def to_python(self, value):
        if isinstance(value, SeasonalDistribution):
            return value

        if value is None:
            return value

        return self.parse_distribution(value)

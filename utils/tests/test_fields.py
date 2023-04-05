from django.core.exceptions import ValidationError
from django.forms import FloatField, BooleanField
from django.test import TestCase

from ..fields import NullableRangeField, NullablePercentageRangeField


class NullableRangeFieldTests(TestCase):

    def test_fields_instantiation(self):
        field = NullableRangeField()
        self.assertEqual(len(field.fields), 3)
        self.assertIsInstance(field.fields[0], FloatField)
        self.assertIsInstance(field.fields[1], FloatField)
        self.assertIsInstance(field.fields[2], BooleanField)

    def test_compress_no_data(self):
        field = NullableRangeField()
        self.assertIsNone(field.compress(None))

    def test_compress_with_data(self):
        field = NullableRangeField()
        data = [10.0, 20.0, False]
        result = field.compress(data)
        self.assertIsInstance(result[0], slice)
        self.assertEqual(result[0].start, 10.0)
        self.assertEqual(result[0].stop, 20.0)
        self.assertEqual(result[1], False)

    def test_compress_with_invalid_data(self):
        field = NullableRangeField()
        data = ["invalid", 20.0, False]

        with self.assertRaises(ValidationError):
            field.clean(data)


class NullablePercentageRangeFieldTests(TestCase):

    def test_fields_instantiation(self):
        field = NullablePercentageRangeField()
        self.assertEqual(len(field.fields), 3)
        self.assertIsInstance(field.fields[0], FloatField)
        self.assertIsInstance(field.fields[1], FloatField)
        self.assertIsInstance(field.fields[2], BooleanField)

    def test_compress_no_data(self):
        field = NullablePercentageRangeField()
        self.assertIsNone(field.compress(None))

    def test_compress_with_data(self):
        field = NullablePercentageRangeField()
        data = [10.0, 20.0, False]
        result = field.compress(data)
        self.assertIsInstance(result[0], slice)
        self.assertEqual(result[0].start, 10.0)
        self.assertEqual(result[0].stop, 20.0)
        self.assertEqual(result[1], False)

    def test_compress_with_invalid_data(self):
        field = NullablePercentageRangeField()
        data = ["invalid", 20.0, False]

        with self.assertRaises(ValidationError):
            field.clean(data)

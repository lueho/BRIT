from django.test import TestCase

from utils.tests.testcases import ScopedSelectionFilterTestMixin

from ..filters import CultureListFilter
from ..models import Culture


class CultureListFilterScopedSelectionTestCase(
    ScopedSelectionFilterTestMixin, TestCase
):
    filterset_class = CultureListFilter
    model = Culture

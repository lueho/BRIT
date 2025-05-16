"""
Custom Django test runner that ensures all initial data is created before running tests.
"""
from django.test.runner import DiscoverRunner
from django.apps import apps

from django.test.runner import DiscoverRunner
from django.core.management import call_command

class InitialDataTestRunner(DiscoverRunner):
    """
    Test runner that loads all initial data using the canonical management command.
    """
    def setup_databases(self, **kwargs):
        result = super().setup_databases(**kwargs)
        call_command("ensure_initial_data")
        return result

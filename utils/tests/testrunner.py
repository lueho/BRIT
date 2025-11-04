"""
Custom Django test runner that ensures all initial data is created before running tests.
"""

import statistics
import time
import unittest

from django.apps import AppConfig
from django.conf import settings
from django.core.management import call_command
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.test.runner import DiscoverRunner

# Module-level flag to ensure we only run ensure_initial_data once per test run
_initial_data_loaded = False


# Signal handler to ensure initial data is loaded for parallel test databases
@receiver(post_migrate)
def ensure_test_initial_data(sender: AppConfig, **kwargs):
    """
    Run ensure_initial_data after migrations complete during test setup.
    This runs once for the first database, then gets mirrored to parallel workers.

    Uses a module-level flag to prevent multiple executions even though this
    signal fires for each app's migrations.
    """
    global _initial_data_loaded

    # Only run during testing
    if not getattr(settings, "TESTING", False):
        return

    # Only run once per test session
    if _initial_data_loaded:
        return

    _initial_data_loaded = True

    # Run ensure_initial_data to create default owner and other initial data
    # Permissions are handled by the post_migrate signal in signals.py
    try:
        call_command("ensure_initial_data")
    except Exception as e:
        # Log the error but don't fail the test setup
        print(f"Warning: Failed to run ensure_initial_data: {e}")


class StopwatchTestResult(unittest.TextTestResult):
    """
    Times test runs and formats the result
    """

    # Collection shared between all result instaces to calculate statistics
    timings = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start = 0
        self.stop = 0
        self.elapsed = 0

    def startTest(self, test):
        self.start = time.time()
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        self.stop = time.time()
        self.elapsed = self.stop - self.start
        self.timings[test] = self.elapsed

    def getDescription(self, test):
        """
        Format test result with timing info
        e.g. `test_add [0.1s]`
        """
        description = super().getDescription(test)
        return f"{description} [{self.elapsed:0.4f}s]"

    @classmethod
    def print_stats(cls):
        """
        Calculate and print timings
        These data are likely skewed, as is normal for reaction time data,
        therefore mean and standard deviation are difficult to interpret. Thus,
        the IQR is used to identify outliers.
        """
        timings = StopwatchTestResult.timings.values()
        count = len(timings)
        mean = statistics.mean(timings)
        stdev = statistics.stdev(timings)
        slowest = max(timings)
        q1, median, q3 = statistics.quantiles(timings)
        fastest = min(timings)
        total = sum(timings)

        print()
        print("Statistics")
        print("==========")
        print("")
        print(f"count: {count:.0f}")
        print(f" mean: {mean:.4f}s")
        print(f"  std: {stdev:.4f}s")
        print(f"  min: {fastest:.4f}s")
        print(f"  25%: {q1:.4f}s")
        print(f"  50%: {median:.4f}s")
        print(f"  75%: {q3:.4f}s")
        print(f"  max: {slowest:.4f}s")
        print(f"total: {total:.4f}s")

        # https://en.wikipedia.org/wiki/Interquartile_range
        iqr = q3 - q1
        q1 - 1.5 * iqr
        slow_threshold = q3 + 1.5 * iqr

        slow_tests = [
            (test, elapsed)
            for test, elapsed in StopwatchTestResult.timings.items()
            if elapsed >= slow_threshold
        ]

        if not slow_tests:
            return
        print()
        print("Outliers")
        print("========")
        print("These were particularly slow:")
        print()
        for test, elapsed in slow_tests:
            print(" ", test, f"[{elapsed:0.4f}s]")


"""
Custom Django test runner that ensures all initial data is created before running tests.

Includes @serial_test decorator: mark test classes or methods for serial execution even when parallel is enabled.
Usage:
    from utils.tests.testrunner import serial_test
    
    @serial_test
    class MySerialTest(TestCase):
        ...
    
    or
    class MyTest(TestCase):
        @serial_test
        def test_something(self): ...

All tests marked with @serial_test will always run after all others, with parallelism forced to 1.
"""


SERIAL_TESTS = set()


def serial_test(obj):
    """
    Decorator to mark a test method or class as serial-only.
    Can be used on test classes or test methods.
    """
    SERIAL_TESTS.add(obj)
    return obj


class StopwatchTestResult(unittest.TextTestResult): ...


class SerialAwareTestRunner(DiscoverRunner):
    """
    Django test runner with serial test support and initial data loading.
    - Runs tests marked with @serial_test serially (after all others, parallel=1).
    - Loads initial data before running tests.
    - Prints timing statistics if --stats is passed.
    """

    def __init__(self, *args, **kwargs):
        self._stats = kwargs.pop("stats", False)
        super().__init__(*args, **kwargs)

    @classmethod
    def add_arguments(cls, parser):
        DiscoverRunner.add_arguments(parser)
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Print timing statistics",
        )

    def get_resultclass(self):
        return StopwatchTestResult

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        # Check if we have any serial tests to handle
        if not SERIAL_TESTS:
            # No serial tests, use Django's standard test runner
            result = super().run_tests(test_labels, extra_tests=extra_tests, **kwargs)
            if self._stats:
                StopwatchTestResult.print_stats()
            return result

        # We have serial tests, so we need custom handling
        # But we still want to use Django's proper test setup
        suite = self.build_suite(test_labels, extra_tests)
        serial_suite = unittest.TestSuite()
        parallel_suite = unittest.TestSuite()

        def is_serial(test):
            # Check if test or its class is marked serial
            test_method = getattr(test, "_testMethodName", None)
            test_class = test.__class__
            if test_class in SERIAL_TESTS:
                return True
            if test_method and hasattr(test_class, test_method):
                method = getattr(test_class, test_method)
                if method in SERIAL_TESTS:
                    return True
            return False

        # Flatten suite to individual tests
        def flatten(suite):
            for item in suite:
                if isinstance(item, unittest.TestSuite):
                    yield from flatten(item)
                else:
                    yield item

        for test in flatten(suite):
            if is_serial(test):
                serial_suite.addTest(test)
            else:
                parallel_suite.addTest(test)

        # Run parallel tests first using Django's proper test execution
        result = 0
        if parallel_suite.countTestCases():
            old_parallel = getattr(self, "parallel", 1)
            result += self.run_suite(parallel_suite, **kwargs)

        # Run serial tests with parallelism disabled
        if serial_suite.countTestCases():
            old_parallel = getattr(self, "parallel", 1)
            self.parallel = 1
            result += self.run_suite(serial_suite, **kwargs)
            self.parallel = old_parallel

        if self._stats:
            StopwatchTestResult.print_stats()

        return result

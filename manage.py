#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Tests must run against the dedicated testrunner settings (isolated
        # caches, eager Celery, seeded initial data). --settings or
        # DJANGO_TEST_SETTINGS_MODULE can still override this.
        os.environ["DJANGO_SETTINGS_MODULE"] = os.environ.get(
            "DJANGO_TEST_SETTINGS_MODULE", "brit.settings.testrunner"
        )
    else:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "brit.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()

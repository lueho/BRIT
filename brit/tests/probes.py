"""Helpers for probing settings modules in clean interpreter subprocesses."""

import os
import subprocess
import sys
from pathlib import Path

_BRIT_PACKAGE_DIR = Path(__file__).resolve().parent.parent

# Settings probes import a fresh ``brit.settings.*`` module under a controlled
# environment. Pre-seeding ``sys.modules`` with a package stub skips executing
# ``brit/__init__.py``, which eagerly builds the Celery app and pulls in boto3
# and friends — roughly half the startup cost of every probe.
LIGHT_PACKAGE_STUB = (
    "import sys, types;"
    "_pkg = types.ModuleType('brit');"
    f"_pkg.__path__ = [{str(_BRIT_PACKAGE_DIR)!r}];"
    "sys.modules['brit'] = _pkg;"
)


def run_settings_probe(script, env=None):
    """Run ``script`` in a clean interpreter and return the CompletedProcess.

    ``env`` values are applied on top of the current environment; a value of
    ``None`` removes the variable.
    """
    environment = os.environ.copy()
    for key, value in (env or {}).items():
        if value is None:
            environment.pop(key, None)
        else:
            environment[key] = value
    return subprocess.run(
        [sys.executable, "-c", LIGHT_PACKAGE_STUB + script],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )

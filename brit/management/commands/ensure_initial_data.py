"""
Management command to ensure all required initial data exists in the database.

This is a centralized way to create initial data outside of migrations,
which helps avoid migration crashes when models change.

Uses an autodiscovery pattern to find and run initialization functions from all installed apps,
making it easier to integrate new apps and promote app autonomy.

Implements topological sorting to handle dependencies between apps.
"""

import importlib
import inspect
import logging
from collections import defaultdict

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Creates all required initial data for the application using autodiscovery with dependency resolution"

    def add_arguments(self, parser):
        parser.add_argument(
            "--app",
            dest="app_label",
            help="Run initialization only for the specified app label",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            dest="list_only",
            help="Only list apps that have initialization functions",
        )
        parser.add_argument(
            "--show-dependencies",
            action="store_true",
            dest="show_dependencies",
            help="Show dependency tree for initialization functions",
        )

    def discover_initializers(self, app_label=None):
        """
        Discover initialization functions from all installed apps.

        Args:
            app_label: Optional label to filter for a specific app

        Returns:
            List of tuples (app_label, init_func, dependencies)
        """
        # Track initialization functions we've found
        found_initializers = []

        # Discover initialization functions from all installed apps
        for app_config in apps.get_app_configs():
            if app_label and app_config.label != app_label:
                continue

            # Try to import a utils module from the app
            module_path = f"{app_config.name}.utils"
            try:
                utils_module = importlib.import_module(module_path)

                # Look for a function matching our naming convention
                init_func = getattr(utils_module, "ensure_initial_data", None)

                # If not found, look for other common patterns
                if not init_func:
                    # List of possible function names to try
                    possible_names = [
                        "ensure_all_data",
                        "initialize_data",
                        "setup_initial_data",
                    ]

                    for name in possible_names:
                        if hasattr(utils_module, name):
                            init_func = getattr(utils_module, name)
                            break

                # If we found an initialization function, store it
                if init_func and callable(init_func):
                    # Check for dependencies
                    dependencies = getattr(
                        utils_module, "INITIALIZATION_DEPENDENCIES", []
                    )
                    found_initializers.append(
                        (app_config.label, init_func, dependencies)
                    )

            except (ImportError, AttributeError):
                # No utils module or no initialization function
                pass

        return found_initializers

    def topological_sort(self, initializers):
        """
        Use topological sorting to determine the order in which to run initializers.

        Args:
            initializers: List of (app_label, init_func, dependencies) tuples

        Returns:
            List of (app_label, init_func) tuples in dependency order
        """
        # Build dependency graph
        graph = defaultdict(list)
        all_nodes = set()

        # Add all apps to the graph, even those with no deps
        for app_label, _, _ in initializers:
            all_nodes.add(app_label)

        # Add dependencies
        for app_label, _, dependencies in initializers:
            for dep in dependencies:
                graph[dep].append(app_label)
                all_nodes.add(dep)  # In case a dependency doesn't have an initializer

        # Topological sort algorithm
        visited = set()
        temp_marked = set()
        sorted_apps = []

        def visit(node):
            if node in temp_marked:
                # This is a circular dependency
                logger.error(f"Circular dependency detected for app '{node}'")
                return

            if node not in visited:
                temp_marked.add(node)

                # Visit all dependencies
                for neighbor in graph.get(node, []):
                    visit(neighbor)

                temp_marked.remove(node)
                visited.add(node)
                sorted_apps.append(node)

        # Visit all nodes
        for node in all_nodes:
            if node not in visited:
                visit(node)

        # Reverse the list to get correct order (dependencies first)
        sorted_apps.reverse()

        # Filter to only apps that have initializers and map to (app_label, func) format
        app_to_func = {app_label: init_func for app_label, init_func, _ in initializers}
        return [(app, app_to_func[app]) for app in sorted_apps if app in app_to_func]

    @transaction.atomic
    def handle(self, *args, **options):
        """
        Execute the command to ensure all required initial data exists.

        This command automatically discovers initialization functions in all installed apps,
        resolves dependencies using topological sorting, and executes them in the correct order.
        """
        logger.info("Ensuring initial data exists...")

        app_label = options.get("app_label")
        list_only = options.get("list_only")
        show_dependencies = options.get("show_dependencies")

        # Discover initializers
        found_initializers = self.discover_initializers(app_label)

        # Handle list-only mode
        if list_only:
            if found_initializers:
                logger.info("Apps with initialization functions:")
                for app_label, _, _ in found_initializers:
                    logger.info(f"  - {app_label}")
            else:
                logger.warning("No apps with initialization functions found")
            return

        # Show dependencies if requested
        if show_dependencies:
            logger.info("App initialization dependencies:")
            for app_label, _, dependencies in found_initializers:
                if dependencies:
                    logger.info(
                        f'  - {app_label} depends on: {", ".join(dependencies)}'
                    )
                else:
                    logger.info(f"  - {app_label} has no dependencies")
            return

        # Sort initializers based on dependencies
        ordered_initializers = self.topological_sort(found_initializers)
        {app for app, _ in ordered_initializers}

        # Show execution order
        logger.info("Execution order:")
        for i, (app_label, _) in enumerate(ordered_initializers, 1):
            logger.info(f"  {i}. {app_label}")

        # Execute all discovered initializers in order
        for app_label, init_func in ordered_initializers:
            logger.info(f"Running initialization for {app_label}...")

            try:
                # Determine function parameters to handle different signatures
                sig = inspect.signature(init_func)
                if "logger" in sig.parameters:
                    # Function expects a logger parameter
                    init_func(logger=logger)
                else:
                    # Standard function with no parameters
                    init_func()

                logger.info(f"Completed initialization for {app_label}")
            except Exception as e:
                logger.error(
                    f"An error occurred during initialization for app '{app_label}': {e}",
                    exc_info=True,  # This will log the full traceback
                )
                # Re-raise the exception to ensure the command fails and stops the release
                raise

        logger.info("Successfully created all initial data")

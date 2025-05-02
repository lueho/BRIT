# Style Guide

This document outlines the coding and documentation conventions for the BRIT project. Following these standards ensures code consistency, readability, and maintainability.

## Python Code
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) for all Python code.
- Use 4 spaces per indentation level.
- Maximum line length: 120 characters.
- Use meaningful variable and function names.
- Add docstrings to all public classes, methods, and functions.
- Group imports in the following order: standard library, third-party, local imports. Separate each group with a blank line.

## Django
- Organize apps by domain or feature.
- Place reusable code in `utils/` or app-specific `utils.py`.
- Use Django’s class-based views unless a function-based view is significantly clearer.
- Name templates with the pattern `<app>/<model>_<action>.html` (e.g., `maps/location_list.html`).
- Use plural for app names (e.g., `users`, `materials`).
- Place static files in the app’s `static/<app>/` directory.

## JavaScript
- Use ES6 syntax and features.
- Prefer vanilla JS; only use jQuery when required by dependencies.
- Use `const` and `let` instead of `var`.
- Use descriptive function and variable names.
- Keep JS files under 200 lines; split into modules if needed.

## HTML & CSS
- Use semantic HTML5 elements.
- Use Bootstrap 4 classes for layout and components.
- Place custom styles in `static/css/` and scope them to avoid conflicts.
- Use BEM naming for custom CSS classes.

## Documentation
- Write clear, concise docstrings and comments.
- Use Markdown for all documentation files.
- Keep documentation up to date with code changes.

## Git & Workflow
- Use feature branches for all development.
- Write descriptive commit messages (imperative mood, e.g., "Add user login form").
- Rebase and squash commits before merging to main.
- Reference issues or tasks in commit messages where applicable.

---

*Consistent style makes collaboration easier and the codebase more maintainable. When in doubt, follow the style of existing code and ask for review.*

_Last updated: 2025-05-02_

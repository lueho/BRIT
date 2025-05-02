# Plan: Incorporating MkDocs into the Project

_Last updated: 2025-05-02_

---

## Objective
Integrate MkDocs as the documentation generator for all finalized, user/developer-facing documentation in the `docs/` directory. Ensure the process aligns with project rules and cleanly separates working notes from published docs.

---

## Steps

### 1. Add MkDocs to Development Requirements
- Add the following to `requirements.txt` (or a `requirements-dev.txt`):
  ```
  mkdocs>=1.6
  mkdocs-material>=9.5
  mkdocstrings[python]>=0.25
  ```
- (Optional) Add `mike` for versioned docs: `mike>=1.1.2`

### 2. Initialize MkDocs Project
- In the project root, run:
  ```sh
  mkdocs new docs
  ```
- Replace the generated `docs/` content with your planned structure (see notes/README.md for recommended layout).

### 3. Configure MkDocs
- Edit/create `mkdocs.yml` in the project root:
  - Set `site_name`, theme (`material`), and navigation.
  - Add plugins:
    ```yaml
    plugins:
      - search
      - mkdocstrings:
          handlers:
            python:
              setup_commands:
                - "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'brit.settings'); django.setup()"
    ```
  - Add markdown extensions for diagrams, admonitions, etc.

### 4. Organize Documentation Content
- Move finalized, user-facing docs from `notes/` to `docs/` as appropriate.
- Structure `docs/` by topic: architecture, apps, API, operations, howtos, references.
- Use auto-generated API docs via mkdocstrings for Python modules.

### 5. Add Build & Serve Commands
- Add a Makefile or management command:
  - `mkdocs build` to generate static site (`docs/site/`)
  - `mkdocs serve` for local preview
- For Docker: add to web service or use a dedicated docs service in `docker-compose.yml`.

### 6. Update .gitignore
- Add `docs/site/` or `docs/_site/` to `.gitignore` to avoid committing build artifacts.

### 7. CI/CD Integration (Optional)
- Add a job to build and (optionally) deploy docs (e.g., GitHub Actions, Netlify, or GitLab CI).
- Use `mkdocs gh-deploy` or Netlify for publishing.

### 8. Team Onboarding
- Add instructions to `docs/README.md` and/or `notes/01_planning/` for how to build, preview, and contribute to documentation.

---

## References
- [MkDocs Documentation](https://www.mkdocs.org/)
- [mkdocs-material](https://squidfunk.github.io/mkdocs-material/)
- [mkdocstrings](https://mkdocstrings.github.io/)

---

## Open Questions / TODOs
- Decide on doc hosting (GitHub Pages, Netlify, etc.)
- Confirm Python API doc generation settings for Django apps
- Review and migrate any legacy docs as needed

---

*This plan should be updated as steps are completed or requirements change.*

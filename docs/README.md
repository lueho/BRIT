# Project Documentation

This directory contains all finalized, user- or developer-facing documentation for the BRIT project. Documentation here is built and published with MkDocs.

## Structure
- `index.md` — Project overview and entry point
- Topical folders: architecture, apps, API, operations, howtos, references
- All content must be finalized and reviewed before moving here from `notes/`

## Building and Previewing Docs
- To build the docs:
  ```sh
  mkdocs build
  ```
- To serve locally for preview:
  ```sh
  mkdocs serve
  ```
- The static site will be generated in `site/` (add this to `.gitignore`)

## Contributing
- Edit or add Markdown files as needed, following project documentation guidelines (see `notes/README.md`).
- Do not duplicate content from `notes/` — move only finalized docs here.

---

*This file is safe to edit or expand as conventions evolve.*

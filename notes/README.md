# Notes Directory

This directory contains working notes, plans, and guides for the BRIT project. Subfolders should be created as needed to organize planning, research, and design documents. Example convention:

- `00_backlog/` — feature/task backlog
- `01_planning/` — step-by-step guides, plans, and RFCs
- `02_design_decisions/` — architecture and decision records
- `03_research/` — research, PoCs, and references

Create subdirectories as needed for organization. All files should be Markdown (`.md`).

---

*This file is safe to edit or expand as conventions evolve.*

---

# Guidelines: Docs vs. Notes

## 1. `docs/` — Project Documentation (User/Developer-Facing)
- **Purpose:**
  - Contains all polished, publishable documentation for users and developers.
  - Examples: architecture overviews, API references, deployment guides, how-tos, changelogs.
- **Structure:**
  - Organized by topic (architecture, apps, API, operations, references, howtos).
  - Each page should be concise (<200 lines); split large topics into subpages.
  - Use MkDocs for navigation and auto-generation from code/docstrings where possible.
- **Workflow:**
  - Only move files to `docs/` when they are finalized, accurate, and reviewed.
  - Remove or archive outdated docs to prevent confusion.
  - Avoid duplication: if a doc exists in both `docs/` and `notes/`, keep only the latest/most complete in the correct place.
- **Formatting:**
  - Use Markdown with clear headings, tables, and diagrams (e.g., Mermaid).
  - Document differences for dev, test, and prod environments when relevant.

## 2. `notes/` — Working Notes (AI/Team-Only)
- **Purpose:**
  - Contains all transient, planning, and internal documents for the team and AI.
  - Examples: feature backlogs, planning guides, research, design decisions, spike results, troubleshooting logs.
- **Structure:**
  - Use numbered subfolders to keep notes organized and ordered:
    - `00_backlog/` — feature/task backlog
    - `01_planning/` — step-by-step guides, plans, RFCs
    - `02_design_decisions/` — architecture and decision records
    - `03_research/` — research, PoCs, references
  - Name files with date + short slug (e.g., `2025-05-02-git-merge-conflict-guide.md`).
- **Workflow:**
  - Use `notes/` for all drafts, scratch work, and in-progress materials.
  - Move finalized, user-facing docs to `docs/` when ready.
  - Delete or archive obsolete notes regularly to keep the directory clean.
- **Formatting:**
  - Markdown only. Keep files short and focused; split if over 200 lines.
  - No fake/mocked data for dev/prod—use only for tests.

## 3. General Principles
- Never duplicate docs between `docs/` and `notes/`. Move or archive as needed.
- Keep all documentation and notes under version control.
- Always update or remove outdated docs/notes after refactoring or major changes.
- Use README.md files in both `docs/` and `notes/` to explain structure and conventions.

---

_Last updated: 2025-05-02_

# Notes Directory

This directory contains all working notes, plans, and guides for the BRIT project. Use this space for:
- Planning and tracking features/tasks
- Design decisions (ADRs)
- Research, PoCs, and technical experiments
- Retrospectives, troubleshooting, and internal guides

## Organization

Recommended subfolder structure:
- `backlog/` — feature/task backlog and priorities
- `planning/` — step-by-step guides, plans, RFCs
- `design_decisions/` — architecture and decision records (ADRs)
- `research/` — research, PoCs, references
- Additional folders as needed for clarity

All files should be Markdown (`.md`). Use clear, dated filenames (e.g., `2025-05-02-feature-x-plan.md`).

---

# Guidelines: Docs vs. Notes

## `docs/` — Project Documentation (User/Developer-Facing)
- Contains only finalized, publishable documentation for users and developers.
- Examples: architecture overviews, API references, deployment guides, how-tos.
- Organized by topic, concise, and maintained via MkDocs.
- Only move files here when reviewed and complete.

## `notes/` — Working Notes (Team/AI-Only)
- Contains all drafts, planning, research, and internal records.
- Use for all in-progress work, troubleshooting, and retrospectives.
- Regularly clean up obsolete notes and move polished docs to `docs/`.

## Principles
- Never duplicate docs between `docs/` and `notes/`.
- Keep everything under version control.
- Update or remove outdated docs/notes after major changes.
- README.md in each directory should explain its structure and conventions.

---

*This file is safe to edit or expand as conventions evolve.*

---

_Last updated: 2025-05-02_

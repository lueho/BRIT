# Context Retention and Memory Offloading

This page defines where durable project context should live so agent memories can stay short and selective.

## Goal

Keep always-injected context small without losing project knowledge.

Use memories for compact pointers and active working constraints. Use repository documentation for durable decisions, recurring interpretation rules, migration notes, and implementation history that should be available on demand.

## What belongs in memory

- **Global execution constraints**
  Docker-first workflow, secrets handling, test runner requirements, and git safety preferences.

- **Currently active task context**
  A short summary of the active branch, unfinished local changes, blocked tests, or immediate rollout risk.

- **Pointers to authoritative docs**
  Prefer "the canonical roadmap is X" over copying detailed roadmap content into memory.

- **Reusable user preferences**
  Communication style, review boundaries, or workflow preferences that should shape every session.

## What belongs in docs instead

- **Architecture and target state**
  Store in app README files or design-decision records.

- **Recurring semantic interpretation rules**
  Store near the relevant ontology, vocabulary, or workflow documentation.

- **Migration and rollout strategy**
  Store in design-decision records or operations notes.

- **One-off import history**
  Store in operations notes when it affects future production work; otherwise rely on git history and issue comments.

- **Completed implementation summaries**
  Store in commit messages, tests, and roadmap progress sections instead of long memories.

## Canonical homes for common context

| Topic | Documentation home |
|---|---|
| Development commands and test defaults | `docs/02_developer_guide/guidelines.md` |
| User-created-object permissions and review workflow | `docs/02_developer_guide/user_created_objects.md` and `docs/02_developer_guide/security_permission_validation.md` |
| Agent/MCP review boundary | `utils/object_management/README.md` and review MCP/skill documentation |
| Waste-collection vocabulary and semantic interpretation rules | `sources/waste_collection/ontology/README.md` |
| Source-domain plugin contract | `sources/README.md` |
| Materials database target state and rollout progress | `docs/04_design_decisions/2026-04-14_materials_database_target_state_plan.md` |
| Maps dataset registry and runtime-adapter roadmap | `docs/04_design_decisions/2026-04-16_dataset_registry_and_federated_geodata_target_state_plan.md` |
| Breadcrumb contract | `brit/README.md` and `docs/04_design_decisions/2026-04-22_breadcrumb_navigation_contract.madr.md` |
| Deployment and production operations | `docs/03_operations/operations.md` |

## Memory pruning policy

When a memory is replaced by documentation:

1. Keep at most one short pointer memory if the topic is still frequently relevant.
2. Delete duplicated implementation summaries after the corresponding code, tests, and docs are committed.
3. Keep production incident/import memories only until they are captured in an operations note, issue, or release checklist.
4. Do not keep full code-path inventories in memory; retrieve them from the codebase when needed.

# Training Management Module — Design Documentation

> **Status:** Design / pre-implementation
> **Target platform:** openIMIS (TASAF / CoreMIS implementation)
> **Backend module:** `openimis-be-training_py` (Django app `training`)
> **Frontend module:** `openimis-fe-training_js` (`@openimis/fe-training`)

This folder contains the **system design and diagrams** for the Training Management
Module. It is written **before** implementation so the models and structure can be
reviewed and so **Phase 2** features can be added later without major refactoring.

## Document index

| # | Document | Purpose |
|---|----------|---------|
| 00 | [00-overview.md](00-overview.md) | Objectives, scope, phasing, glossary |
| 01 | [01-architecture.md](01-architecture.md) | How the module plugs into openIMIS (BE + FE assembly), component & deployment diagrams |
| 02 | [02-data-model.md](02-data-model.md) | Entity Relationship Diagram, every model & field, Phase-2 extension points |
| 03 | [03-graphql-api.md](03-graphql-api.md) | Queries, mutations, conflict-check & dashboard API |
| 04 | [04-permissions.md](04-permissions.md) | Rights matrix (MMEEAA codes) and role mapping |
| 05 | [05-conflict-detection.md](05-conflict-detection.md) | Hard vs soft conflict rules, algorithm, sequence diagram |
| 06 | [06-workflow-status.md](06-workflow-status.md) | Training status state machine and allowed transitions |
| 07 | [07-frontend.md](07-frontend.md) | Screens, routes, redux store shape, menu contributions |
| 08 | [08-phasing-roadmap.md](08-phasing-roadmap.md) | Phase 1 deliverables vs Phase 2 roadmap and how the schema anticipates them |
| 09 | [09-runbook.md](09-runbook.md) | Migration plan, build, and manual test commands |
| 10 | [10-user-manual.md](10-user-manual.md) | **End‑user manual** — how to create/manage trainings, statuses, assignments, files |
| 11 | [11-troubleshooting.md](11-troubleshooting.md) | **Troubleshooting & FAQ** — rights, pickers, date/relay‑id/filter gotchas and fixes |
| — | [MODULE_OVERVIEW.md](MODULE_OVERVIEW.md) | **As‑built overview** — what ships today, key concepts, file map (start here) |

## How to read the diagrams

All diagrams are written in [Mermaid](https://mermaid.js.org/). They render natively
on GitHub, in VS Code (with the *Markdown Preview Mermaid* extension), and in the
docs hub. A plain-text fallback is included where helpful.

## One-paragraph summary

The Training Module lets TASAF users plan, schedule, staff, document, and review
trainings across the TASAF programme areas and the openIMIS location hierarchy
(Region → District/Council → Ward → Village/Shehia → PAA). It follows openIMIS
modular conventions exactly: `HistoryModel`-based UUID entities with soft delete and
audit fields, Graphene CRUD with `OrderedDjangoFilterConnectionField`, per-entity
service classes with service signals, `MMEEAA` rights, and a React/Redux frontend
module contributed into the assembly via `openimis.json`. Phase 1 delivers the core
usable module (trainings, categories, trainers, assignments, participants/attendance,
materials, evidence, conflict checks, calendar, weekly view, status workflow, and a
dashboard). Phase 2 (evaluation, certificates, plan-vs-actual, budgets, action points,
needs assessment, cohorts, notifications, performance linkage) is **designed for** via
explicit extension points but **not implemented** now.

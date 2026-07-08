# openimis-be-training_py

openIMIS Backend **Training Management** module for the TASAF / CoreMIS
implementation.

Plan, schedule, staff, document and review trainings across TASAF programme areas and
the openIMIS location hierarchy (Region → District/Council → Ward → Village/Shehia →
PAA), with conflict detection, a status workflow, participants/attendance, materials
& evidence uploads, a calendar and a dashboard.

> **Full design & diagrams:** see [`docs/`](docs/README.md). This module ships
> **Phase 1**; Phase 2 (evaluation, certificates, budgets, …) is designed-for but not
> implemented — see [`docs/08-phasing-roadmap.md`](docs/08-phasing-roadmap.md).

## Models

`TrainingCategory`, `TrainerProfile`, `Training`, `TrainingAssignment`,
`TrainingParticipant`, `TrainingMaterial`, `TrainingEvidence` — all extend
`core.models.HistoryModel` (UUID PK, soft delete, audit, `json_ext`), each with a
`*Mutation` journal table.

## Rights (module `21`)

`2101xx` Training · `2102xx` Category · `2103xx` Trainer · `2104xx` Assignment ·
`2105xx` Material · `210601` Dashboard/Calendar · `2107xx` Participant ·
`2108xx` Evidence. Defaults in `training/apps.py::DEFAULT_CONFIG`, overridable via
`core.ModuleConfiguration`. Granted to the IMIS Administrator role on migrate.

## Install

```bash
pip install -e ../openimis-be-training_py
python manage.py makemigrations training
python manage.py migrate
```

Register in `openimis-be_py/openimis.json` and `modules-requirements.txt`
(`-e ../openimis-be-training_py`). See [`docs/09-runbook.md`](docs/09-runbook.md).

## GraphQL

Queries: `training`, `trainingCategory`, `trainerProfile`, `trainingAssignment`,
`trainingParticipant`, `trainingMaterial`, `trainingEvidence`, `trainingCalendar`,
`trainingConflicts`, `trainingSummary`.
Mutations: per-entity create/update/delete + Training status workflow
(`submit/approve/reject/schedule/start/complete/cancel/close`).
File upload/download via DRF endpoints under `/api/training/...`.

## Developer Guide

Start with `training/models.py` for the event, session, participant, material,
evidence and mutation-journal entities. Workflow rules, conflict checks, dashboard
summary and QR self check-in behavior live in `training/services.py`; GraphQL
mutations are in `training/gql_mutations.py`; upload/download/check-in endpoints
are in `training/views.py`.

The module uses rights in the `21xxxx` range, defined in
`training/apps.py::DEFAULT_CONFIG`. Keep those values aligned with the frontend
constants and menu filters.

The frontend companion is `openimis-fe-training_js`. It expects the backend
GraphQL names and REST paths under `/api/training/...` to remain stable. Run
`python manage.py makemigrations training` only for schema changes, then
`python manage.py migrate`.

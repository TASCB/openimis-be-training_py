# Training Management Module — Overview (as built)

> **Status:** Phase 1 implemented (backend + frontend).
> **Backend:** `openimis-be-training_py` (Django app `training`, module number **21**).
> **Frontend:** `openimis-fe-training_js` (`@openimis/fe-training`).
> For the original *design* documents see [00-overview.md](00-overview.md) onward; this
> file describes what actually ships today.

## 1. What the module does

The Training Management Module lets TASAF / CoreMIS users **plan, schedule, staff,
document, and review trainings** across TASAF programme areas and the openIMIS
location hierarchy. It is a full workflow module, not bare CRUD:

- Create / edit / list / soft‑delete trainings with filters and pagination.
- Classify each training by **Programme Area** (a `TrainingCategory`) and optionally
  a **PAA reference** and a **Location**.
- Maintain reusable **Trainer Profiles** (internal staff or external).
- **Assign** trainers / staff to a training with a role and assignment status.
- Track **Participants** and their **attendance**.
- Upload **Materials** (before/during) and **Evidence** (after).
- Get **conflict warnings** (trainer / venue / staff double‑booking) that hard‑block save.
- Drive a **status workflow** (Draft → … → Closed).
- View a **Calendar** (month / week) and a summary **Dashboard**.

## 2. Key concepts (read this first)

| Concept | What it is | Stored as |
|---|---|---|
| **Programme Area** | The TASAF business/functional area a training belongs to (Targeting, Enrollment, Payment, Grievance, Public Works, Livelihoods, Case Management, M&E, Safeguards, Data Quality, Community, General Admin). Chosen from a **seeded list**. | `Training.category` → `TrainingCategory` |
| **PAA** | *Productive Asset Area* / programme operational area tied to a location. A **free‑text reference** on the training (and a participant type, "PAA Representative"). **Not** the same as Programme Area. | `Training.paa_reference` (text) |
| **Location** | openIMIS location hierarchy (Region → District/Council → Ward → Village/Shehia). | `Training.location` → `location.Location` |
| **Trainer Profile** | A reusable person record you can assign to many trainings. | `TrainerProfile` |
| **Assignment** | A trainer **or** staff user linked to one training, with a role + status. | `TrainingAssignment` |

> **Programme Area vs PAA** — Programme Area *classifies* the training (pick from a
> list); PAA *references* the operational area/asset it relates to (typed in). They
> are independent fields.

## 3. Entities

`TrainingCategory`, `TrainerProfile`, `Training`, `TrainingAssignment`,
`TrainingParticipant`, `TrainingMaterial`, `TrainingEvidence`, plus one `*Mutation`
journal table per entity. All extend `core.models.HistoryModel` (UUID PK, soft delete
via `is_deleted`, `version`, `json_ext`, audit users/timestamps, `simple_history`
shadow table). Full ERD in [02-data-model.md](02-data-model.md).

## 4. Status workflow

```
Draft ──submit──▶ Submitted ──approve──▶ Approved ──schedule──▶ Scheduled
  ▲                   │                                              │
  │revise             └──reject──▶ Rejected ──revise──▶ Draft       start
  │                                                                  ▼
Rejected                                                          Ongoing ──complete──▶ Completed ──close──▶ Closed

cancel: allowed from Draft / Approved / Scheduled / Ongoing  ──▶ Cancelled
```

Transitions are enforced server‑side in `TrainingService.transition`
(`STATUS_TRANSITIONS`). Re‑scheduling re‑checks hard conflicts. Details in
[06-workflow-status.md](06-workflow-status.md).

## 5. Where things live

| Layer | File(s) |
|---|---|
| Models | `training/models.py` |
| Services (CRUD + transition + conflict + summary) | `training/services.py` |
| Validation | `training/validations.py` |
| GraphQL types / filters | `training/gql_queries.py` |
| GraphQL Query + Mutation | `training/schema.py` |
| Mutations | `training/gql_mutations.py` |
| File upload (DRF) | `training/views.py`, `training/urls.py` |
| Config + rights/category seeding | `training/apps.py` |
| FE actions / reducer | `openimis-fe-training_js/src/actions.js`, `reducer.js` |
| FE pages | `src/pages/*` (Trainings, Training, Trainers, Trainer, Calendar, Dashboard) |
| FE components / pickers | `src/components/*`, `src/pickers/*` |

## 6. Permissions (rights)

Right codes `2101xx`–`2108xx` (see [04-permissions.md](04-permissions.md)). On
`post_migrate` they are granted to the **IMIS Administrator** system role (id 64) and
the 12 default programme areas are seeded. Custom roles must be granted these rights
explicitly. **Rights are loaded at login — grant rights, then log out/in.**

## 7. Frontend conventions

The FE follows openIMIS practice: `core.DatePicker` for dates, `NumberInput` for
numbers, `ConstantBasedPicker` for enums, `Autocomplete` + `useGraphqlQuery` for async
pickers, `Searcher` for lists, `coreConfirm` for delete dialogs, `ProgressOrError` for
fetch states, and `formatDateFromISO` / `formatDateTimeFromISO` for display. See
[07-frontend.md](07-frontend.md).

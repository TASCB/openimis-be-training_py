# 03 — GraphQL API

The module contributes a `Query` and a `Mutation` class that openIMIS concatenates
into the global schema (same mechanism as `payment_cycle`). All list queries use
`OrderedDjangoFilterConnectionField` → Relay connections with `filter`, `orderBy`,
pagination (`first/last/before/after`), and `totalCount`.

## 1. Queries

| Query | Returns | Key args | Right |
|-------|---------|----------|-------|
| `training` | `TrainingGQLType` connection | code, title, status, category_Id, location_Id, start/end ranges, `search`, `client_mutation_id` | `210101` |
| `trainingCategory` | `TrainingCategoryGQLType` connection | code, name, is_active | `210201` |
| `trainerProfile` | `TrainerProfileGQLType` connection | code, full_name, trainer_type, is_active | `210301` |
| `trainingAssignment` | `TrainingAssignmentGQLType` connection | training_Id, trainer_Id, role, status | `210401` |
| `trainingParticipant` | `TrainingParticipantGQLType` connection | training_Id, participant_type, attendance_status | `210701` |
| `trainingMaterial` | `TrainingMaterialGQLType` connection | training_Id, file_type | `210501` |
| `trainingEvidence` | `TrainingEvidenceGQLType` connection | training_Id, evidence_type | `210801` |
| `trainingConflicts` | `[TrainingConflictGQLType]` | trainingId?, startDatetime, endDatetime, venue, locationId, trainerIds[], staffUserIds[] | `210101` |
| `trainingSummary` | `TrainingSummaryGQLType` | dateFrom?, dateTo?, locationId? | `210601` |
| `trainingCalendar` | `TrainingGQLType` connection (range-bounded) | dateFrom, dateTo, status, trainer, category, location | `210601` |

### `TrainingConflictGQLType`
```graphql
type TrainingConflictGQLType {
  type: String!        # TRAINER | VENUE | STAFF | LOCATION
  hard: Boolean!       # true => blocks save
  message: String!     # human-readable, e.g. "Trainer John Doe is already assigned to Training ABC 10:00–13:00"
  conflictingTrainingId: String
  conflictingTrainingCode: String
  subjectId: String    # trainer/staff/venue identifier
  subjectLabel: String
}
```

### `TrainingSummaryGQLType` (dashboard)
```graphql
type TrainingSummaryGQLType {
  totalTrainings: Int
  trainingsThisWeek: Int
  upcomingTrainings: Int
  ongoingTrainings: Int
  completedTrainings: Int
  cancelledTrainings: Int
  activeTrainers: Int
  byStatus: [StatusCountGQLType]      # { status, count }
  byCategory: [CategoryCountGQLType]  # { categoryId, categoryName, count }
}
```

## 2. Mutations

### CRUD (per entity — Create / Update / Delete)
`createTraining`, `updateTraining`, `deleteTraining`,
`createTrainingCategory` / `update…` / `delete…`,
`createTrainerProfile` / `update…` / `delete…`,
`createTrainingAssignment` / `update…` / `delete…`,
`createTrainingParticipant` / `update…` / `delete…`,
`deleteTrainingMaterial`, `deleteTrainingEvidence`
(material/evidence **create** is the DRF multipart upload, see §3).

Each follows the openIMIS pattern:
`BaseHistoryModelCreateMutationMixin / …UpdateMutationMixin / …DeleteMutationMixin + BaseMutation`,
with `_validate_mutation` checking the right and `_mutate` delegating to the service
and journaling via `<Entity>Mutation.object_mutated`. `deleteTraining` performs a
**soft delete** (sets `is_deleted=True`).

### Status-workflow mutations (Training is not bare CRUD)
| Mutation | From → To | Right |
|----------|-----------|-------|
| `submitTraining` | DRAFT → SUBMITTED | `210102/03` |
| `approveTraining` | SUBMITTED → APPROVED | `210110` (training.approve) |
| `rejectTraining` | SUBMITTED → REJECTED | `210110` |
| `scheduleTraining` | APPROVED → SCHEDULED | `210103` |
| `startTraining` | SCHEDULED → ONGOING | `210103` |
| `completeTraining` | ONGOING → COMPLETED | `210103` |
| `cancelTraining` | (SCHEDULED/ONGOING/APPROVED) → CANCELLED | `210103` |
| `closeTraining` | COMPLETED → CLOSED | `210103` |
| `changeTrainingStatus` | generic guarded transition | per-target |

These can be implemented either as discrete mutations (Phase-1 default) **or** routed
through `tasks_management` maker-checker later — the service exposes
`transition(training, target_status, user)` so the GraphQL layer stays thin.

### `createTraining` input (illustrative)
```graphql
input CreateTrainingInput {
  code: String!
  title: String!
  description: String
  categoryId: UUID
  startDatetime: DateTime!
  endDatetime: DateTime!
  venue: String
  locationId: Int
  paaReference: String
  status: TrainingStatusEnum   # defaults DRAFT
  expectedParticipants: Int
  ignoreConflicts: Boolean     # soft conflicts only; hard conflicts always block
}
```

## 3. File upload / download (DRF, not GraphQL)

GraphQL is JSON; binary uploads use DRF multipart endpoints (mirrors how
`payment_cycle` exposes CSV via `APIView`). Declared in `training/urls.py`:

| Method | Path | Purpose | Right |
|--------|------|---------|-------|
| `POST` | `/api/training/materials/upload/` | upload a `TrainingMaterial` (multipart: `training_id`, `file`, `description`) | `210502` |
| `GET` | `/api/training/materials/<uuid>/download/` | stream the material file | `210501` |
| `POST` | `/api/training/evidence/upload/` | upload a `TrainingEvidence` (multipart: `training_id`, `evidence_type`, `file`, `description`) | `210802` |
| `GET` | `/api/training/evidence/<uuid>/download/` | stream the evidence file | `210801` |
| `POST` | `/api/training/participants/import/` | (optional) bulk participant CSV import | `210703` |

After upload the FE refreshes the GraphQL `trainingMaterial` / `trainingEvidence`
list to show the new row with its download link.

## 4. Resolver conventions

- Permission check at the top of every resolver (`user.has_perms(TrainingConfig.<right>)`).
- `gql_optimizer.query(qs, info)` to avoid N+1 on FK joins (category, location, trainer).
- `client_mutation_id` arg → `wait_for_mutation` + filter on `mutations__mutation__client_mutation_id` so the FE can read-back a just-created row (same as `payment_cycle`).
- Default queryset excludes `is_deleted=True` (soft delete) unless explicitly requested.

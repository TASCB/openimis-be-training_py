# Consolidated System Diagrams

Quick-reference copies of the key diagrams. Full context lives in the numbered docs.

## 1. High-level system context (ASCII fallback)

```
                +-------------------------------------------------------+
                |                 openIMIS Frontend (SPA)               |
                |   fe-core  |  fe-location  |  *** fe-training (NEW) ***|
                +------------------------+------------------------------+
                                         |  GraphQL  +  multipart upload
                                         v
                +------------------------+------------------------------+
                |                 openIMIS Backend (Django)             |
                |   core  |  location  |  tasks_management(opt)         |
                |                *** training (NEW) ***                 |
                |   models • schema • services • conflict • DRF upload  |
                +------------+-----------------------------+------------+
                             |                             |
                             v                             v
                      +------+------+              +-------+--------+
                      | PostgreSQL  |              | MEDIA storage  |
                      | training_*  |              | materials /    |
                      | tables      |              | evidence files |
                      +-------------+              +----------------+
```

## 2. Module integration (Mermaid)

```mermaid
flowchart LR
    FET["fe-training"] -->|GraphQL| BET["be: training"]
    FET -->|multipart upload| BET
    FEC["fe-core"] --- FET
    FEL["fe-location"] --- FET
    BEC["core"] --- BET
    BEL["location"] --- BET
    BTM["tasks_management (opt)"] -. phase2 .- BET
    BET --> PG[("PostgreSQL")]
    BET --> FS[("MEDIA storage")]
```

## 3. ERD (Mermaid) — see 02-data-model.md for full attributes

```mermaid
erDiagram
    TRAINING_CATEGORY ||--o{ TRAINING : categorises
    TRAINING ||--o{ TRAINING_ASSIGNMENT : has
    TRAINER_PROFILE ||--o{ TRAINING_ASSIGNMENT : "assigned via"
    TRAINING ||--o{ TRAINING_PARTICIPANT : has
    TRAINING ||--o{ TRAINING_MATERIAL : has
    TRAINING ||--o{ TRAINING_EVIDENCE : has
    LOCATION ||--o{ TRAINING : "located at"
```

## 4. Status state machine (Mermaid) — see 06-workflow-status.md

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> SUBMITTED
    SUBMITTED --> APPROVED
    SUBMITTED --> REJECTED
    REJECTED --> DRAFT
    APPROVED --> SCHEDULED
    SCHEDULED --> ONGOING
    ONGOING --> COMPLETED
    COMPLETED --> CLOSED
    DRAFT --> CANCELLED
    APPROVED --> CANCELLED
    SCHEDULED --> CANCELLED
    ONGOING --> CANCELLED
    CLOSED --> [*]
    CANCELLED --> [*]
```

## 5. Conflict-check sequence (Mermaid) — see 05-conflict-detection.md

```mermaid
sequenceDiagram
    participant FE
    participant GQL as trainingConflicts / createTraining
    participant SVC as ConflictService
    participant DB
    FE->>GQL: input (dates, venue, trainers, staff, location)
    GQL->>SVC: check()
    SVC->>DB: overlap queries
    DB-->>SVC: rows
    SVC-->>GQL: [{type, hard, message}]
    GQL-->>FE: red=block (hard) / amber=warn (soft)
```

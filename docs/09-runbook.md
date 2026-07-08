# 09 — Runbook (install, migrate, build, test)

> **Two environments:**
> - **Local (developer machine):** the backend (Django) and frontend (Node) run **on the
>   host**; **only the database runs in Docker**, published on **`localhost:5434`**
>   (`openimis-dist_dkr-db-1`). Run `manage.py`/`npm` directly on the host.
> - **Server:** backend and frontend run **inside Docker** — use the
>   `docker compose exec <service> …` variants.
>
> Local paths: backend entrypoint `openimis-be_py/openIMIS/manage.py`, host virtualenv
> `openimis-be_py/venv`. The repo `.env` has `DB_HOST=db` / `DB_PORT=5432` (the in-Docker
> view); for **host** runs point Django at the published port (`DB_HOST=localhost`,
> `DB_PORT=5434`).

## 1. Register the modules

**Backend** — `openimis-be_py/openimis.json`, append to `modules`:
```json
{ "name": "training", "pip": "-e /home/jeffharan/projects/tasafMis/openimis-dist_dkr/openimis-be-training_py" }
```
**Backend** — `openimis-be_py/modules-requirements.txt`, append:
```
-e ../openimis-be-training_py
```
**Frontend** — `openimis-fe_js/openimis.json`, append to `modules`:
```json
{ "name": "TrainingModule", "npm": "@openimis/fe-training@file:../openimis-fe-training_js" }
```

## 2. Install + migrate (backend)

### Local (host — DB in Docker on localhost:5434)
```bash
cd openimis-be_py/openIMIS
source ../venv/bin/activate                 # host virtualenv
export DB_HOST=localhost DB_PORT=5434        # reach the Dockerised DB's published port

pip install -e ../../openimis-be-training_py # editable install of the module

python manage.py makemigrations training     # generate 0001_initial from the models
python manage.py migrate                     # create training_* tables; post_migrate
                                             # seeds 21xxxx rights + programme areas
```

### Server (backend in Docker)
```bash
docker compose exec backend pip install -e ../openimis-be-training_py
docker compose exec backend python manage.py makemigrations training
docker compose exec backend python manage.py migrate
```

> **Seeding is automatic & idempotent.** Rights (granted to the IMIS Administrator
> role) and the default TASAF programme areas are seeded by a `post_migrate` signal in
> `training/apps.py` — there is **no** hand-shipped `0002`/`0003` data migration (that
> would break `makemigrations`, since `0001_initial` is generated locally, not shipped).
> Just run `makemigrations` then `migrate`.

## 3. Build the frontend

### Local (host)
```bash
# build the module package on the host
cd openimis-fe-training_js && npm install && npm run build

# wire into the assembly and run/build it on the host
cd ../openimis-fe_js
npm install            # picks up @openimis/fe-training from openimis.json
npm start              # dev server, or: npm run build
```

### Server (frontend in Docker)
```bash
docker compose build frontend && docker compose up -d frontend
```

## 4. Verify GraphQL

Open `/api/graphql` (GraphiQL) and run:
```graphql
query { training(first: 5) { totalCount edges { node { id code title status } } } }
query { trainingSummary { totalTrainings trainingsThisWeek byStatus { status count } } }
mutation {
  createTraining(input: {
    code: "PAY-2026-001", title: "Paylist approval refresher",
    startDatetime: "2026-06-20T10:00:00Z", endDatetime: "2026-06-20T13:00:00Z",
    venue: "TASAF HQ Room 2", status: DRAFT
  }) { clientMutationId internalId }
}
```

## 5. Manual test checklist

- [ ] Trainings menu visible to a user with `210101`, hidden without it.
- [ ] Create → appears in list; soft delete sets `is_deleted` (row disappears, history kept).
- [ ] Conflict: create two trainings, same trainer, overlapping time → save **blocked** with message.
- [ ] Soft conflict: same location, overlapping → **amber warning**, save allowed.
- [ ] Status: Draft → Submit → Approve → Schedule → Start → Complete → Close transitions enforced; illegal jump rejected.
- [ ] Upload a PDF material; download link returns the file.
- [ ] Upload evidence (report); appears under Evidence tab.
- [ ] Add participants, set attendance; counts reflected on dashboard.
- [ ] Calendar shows events coloured by status; click opens detail.
- [ ] Dashboard cards + by-status + by-category match the data.

## 6. Rollback

```bash
# local (host): from openimis-be_py/openIMIS with venv active + DB_HOST/PORT set
python manage.py migrate training zero   # drops training_* tables
# server: docker compose exec backend python manage.py migrate training zero
```
> `migrate … zero` reverses the schema; the `post_migrate` rights/category seeding is
> not auto-revoked (it only ever *adds* missing rows). Remove the manifest entries (§1)
> and `pip uninstall openimis-be-training` to fully detach.

## 7. Run module tests

Tests use a throwaway test DB (Django creates/destroys it) — run on the host with the
venv active, or in the backend container on the server.

```bash
# local (host): cd openimis-be_py/openIMIS && source ../venv/bin/activate
python manage.py test training            # services + conflict + transition unit tests
# server: docker compose exec backend python manage.py test training
```

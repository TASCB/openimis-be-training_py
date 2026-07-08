# 11 — Troubleshooting & FAQ

Common issues seen while operating/developing the Training module, with root cause and
fix. Most are openIMIS conventions worth knowing for any module.

## A. "I can't see the menu / the Save button is disabled"

**Cause.** Your logged‑in session's rights don't include the training rights
(`2101xx`–`2108xx`). Rights are seeded to the *IMIS Administrator* role on
`post_migrate`, but the **frontend loads rights at login** — a session created before
the rights existed won't have them.

**Fix.**
1. Confirm your role has the rights (admin role does by default).
2. **Log out and log back in** to reload `i_user.rights`.
3. Custom (non‑admin) roles must be **granted `2101xx`–`2108xx` explicitly** — seeding
   only targets system role 64.

Quick check in the browser console on a training page:
```js
window.store?.getState().core.user.i_user.rights.filter(r => r >= 210101 && r <= 210804)
```
Empty array ⇒ stale session ⇒ re‑login.

## B. Save stays disabled even though the form is filled

`canSave()` = *can edit* **and** *all mandatory fields set* **and** *no hard conflict*.

- **Dates.** Use the **date picker**; Start and End must both be set (End ≥ Start).
- **Hard conflict.** A red conflict banner blocks save — change the time/venue/trainer
  or resolve the clash.
- **Editable only in Draft/Rejected.** In other statuses the header is read‑only by
  design; use the workflow buttons.

## C. "Programme Area shows no options"

**Cause.** The picker queried the connection field with a bare `search:` argument, which
is **not a valid argument** on `trainingCategory` / `trainerProfile`. The query errored
and returned nothing.

**Fix (implemented).** Route the search term through a real filter field instead:
`name_Icontains: $search` for categories, `fullName_Icontains: $search` for trainers.
General rule: **openIMIS connection fields have no generic `search` arg** — filter via a
declared `filter_fields` lookup (`<field>_Icontains`, etc.).

If the list is still empty, verify categories exist/are active:
```sql
SELECT code, is_active FROM training_trainingcategory;  -- 12 rows seeded by default
```
Re‑seeding happens on migrate when `seed_programme_areas` is true and at least one user
exists.

## D. `Syntax Error GraphQL … Expected Name, found =` on save (e.g. `locationId: TG9j…=`)

**Cause.** Pickers and nested objects expose ids as **relay global ids** (base64
`"Type:pk"`, e.g. `TG9jYXRpb25HUUxUeXBlOjE=`). Sent verbatim, an unquoted `locationId`
breaks GraphQL syntax, and UUID ids fail validation.

**Fix (implemented).** Use the right id form per context — this is the key rule:

| Context | Backend type | Id form | Helper |
|---|---|---|---|
| **Mutation inputs** | `graphene.UUID` / `Int` | **decoded** raw pk | `decId()` |
| **Connection FK filters** (`trainingId`, `categoryId`, `assignments_Trainer_Id`, …) | graphene‑django **`GlobalIDFilter`** | **encoded** relay global id | `encId('TypeGQLType', uuid)` / the picker's `v.id` |
| **`id` (pk) filter** | UUIDField → plain `UUIDFilter` | raw uuid | — |
| Query scalar args (`trainingConflicts` `trainerIds`, `locationId`) | `UUID` / `Int` | decoded | `decId()` |

Symptoms of getting it wrong: an unquoted encoded id → *"Expected Name, found ="*; a raw
uuid sent to a FK filter → *"Invalid ID specified"*. Reason: graphene‑django maps every
`ForeignKey` filter to a `GlobalIDFilter` that base64‑decodes `"Type:pk"` (the type part
is ignored).

## E. `Unknown argument "training_Id" … Did you mean "trainingId"?`

**Cause.** Filter argument names are **auto‑camelCased** from the model field, and the FE
used the wrong casing.

**Naming rule** (graphene `to_camel_case`):
- single‑underscore field, exact lookup → plain camelCase: `training_id` → `trainingId`,
  `category_id` → `categoryId`.
- non‑exact lookup → `_Capitalized` suffix: `start_datetime` + `gte` → `startDatetime_Gte`.
- `__` relation step → `_Capitalized` segment: `assignments__trainer__id` →
  `assignments_Trainer_Id`.

**Fix (implemented).** Corrected the child fetches and filters; added the
`assignments__trainer__id` filter to `TrainingGQLType` (with `.distinct()` in the
resolver) so the searcher's trainer filter works.

## F. Date field showed a `--:-- --` time placeholder / wouldn't accept input

**Cause.** A raw `<input type="datetime-local">` only emits a value when *both* date and
time are filled, so a date‑only entry produced an empty value.

**Fix (implemented).** Use **`core.DatePicker`** (date‑only, openIMIS‑standard). The FE
maps the chosen day to a datetime for the model's `DateTimeField` (Start → 00:00:00,
End → 23:59:59, in local time).

## G. Dates display with odd times (e.g. `12:00:00 AM`)

Use the core display helpers, not a custom formatter: `formatDateFromISO` for
date‑only fields (trainings), `formatDateTimeFromISO` for true timestamps (file
`dateCreated`).

## H. Conflict checks behave unexpectedly

- Conflict detection is configurable: `conflict_check_enabled`, `conflict_hard_types`
  (default `TRAINER`, `VENUE`, `STAFF`), `conflict_soft_types` (default `LOCATION`).
- Only **active** assignments (Assigned/Confirmed) and **non‑terminal** trainings
  (not Cancelled/Rejected/Closed) participate. See
  [05-conflict-detection.md](05-conflict-detection.md).

## I. Module not appearing at all

- Backend registered in `openimis-be_py/openimis.json` (entry `training`).
- Frontend registered in the FE assembly (`openimis.json` / module list).
- Run `migrate` (creates tables, seeds rights + categories via `post_migrate`).
- Restart backend; rebuild/restart the FE bundle.

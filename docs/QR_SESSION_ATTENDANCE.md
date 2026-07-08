# QR Session Attendance — Self Check-in

**Module:** `openimis-be-training_py` + `openimis-fe-training_js`
**Status:** design approved 2026-06-30; implementation in progress
**Goal:** let training attendees **self check-in by scanning a QR code** instead of being
typed in by an officer. Each scan adds the attendee to the system and marks them present.

---

## 1. Current modality (before this feature)

Attendance is **100% staff-driven and authenticated**:

- A `Training` has many `TrainingParticipant` rows
  (`full_name, phone, email, organization, title, participant_type, internal_user?, location?,
  attendance_status, attendance_remarks`). `attendance_status` ∈
  **INVITED → CONFIRMED → ATTENDED / ABSENT / REPLACED**.
- An officer **types each attendee in by hand** in the Participants panel
  (`TrainingParticipantsPanel.js`) → `CreateTrainingParticipantMutation` (GraphQL, right `210702`).
- The officer **manually flips each row's `attendance_status`** (`UpdateTrainingParticipantMutation`).
- Optionally a scanned, signed paper sheet is uploaded as `Evidence (ATTENDANCE_SHEET)`.
- Attendees are **not** openIMIS users; there is **no public/anonymous path**.

Pain: slow double data-entry for big trainings, error-prone, no self-service, no real-time roster.

---

## 2. Approved decisions

| # | Decision | Choice |
|---|---|---|
| Fields the attendee enters | — | **full_name, gender, phone, email, organization, title** |
| Anti-fraud | no SMS gateway | **registration open/close window + (phone, session) de-dupe + rate-limit + lightweight captcha** (honeypot + math/Turnstile-style; no paid SMS/OTP) |
| Verification | — | **Auto-count** (self check-ins count immediately; `self_registered` flag only for provenance, no staff-approval gate) |
| Identity link | — | **Free text** (no Individual-registry matching) |
| **Token scope** | — | **One QR per SESSION/day** (introduces `TrainingSession`) |

---

## 3. Data model (per-session)

### New entity `TrainingSession` (child of `Training`)
`training FK, title ("Day 1"), session_date, start_time, end_time, sequence, venue?` plus the
QR/registration fields:
- `registration_token` — random, unique, indexed (the value embedded in the QR; **never** the UUID)
- `registration_open` — bool, default **False** (closed until the officer opens it)
- `registration_opens_at` / `registration_closes_at` — optional time window
Each session owns **its own token/QR**.

### `TrainingParticipant` additions
- `session` FK → `TrainingSession` (**nullable**; `null` = legacy manual whole-training entry)
- `gender` (choices M/F/OTHER or reuse core gender codes)
- `self_registered` (bool, default False)
- `check_in_method` (`MANUAL` | `QR`, default `MANUAL`)
- `registered_at` (datetime, set on self check-in)

**De-dupe key = (phone, session).** Attendance is naturally per-session, so one
`TrainingParticipant` row per (person, session) **reuses all existing attendance machinery**
(panel, searcher, `attendance_status`); the searcher just gains a session filter. A person who
attends 3 days = 3 rows (one per session) — the natural per-session register. This avoids a 3rd
"SessionAttendance" table and keeps the change openIMIS-idiomatic.

---

## 4. Public check-in endpoint (token = the **session** token)

New `training/urls.py`, DRF, `permission_classes=[AllowAny]` — the **only** public surface;
everything else stays authenticated GraphQL.

- `GET  /api/training/checkin/<token>` → public summary: training title, session title/date/venue,
  `is_open`. (Drives the form header; reveals nothing sensitive.)
- `POST /api/training/checkin/<token>` → body `{full_name, gender, phone, email, organization,
  title, captcha, hp}`:
  1. resolve token → session; **404** if unknown.
  2. reject if `registration_open` false or outside `opens_at/closes_at` window.
  3. honeypot (`hp` must be empty) + captcha check + IP rate-limit.
  4. **de-dupe** by (normalised phone, session) → if exists, return "already checked in".
  5. create `TrainingParticipant(session=…, training=session.training, attendance_status=ATTENDED,
     self_registered=True, check_in_method=QR, registered_at=now, …fields)`.
  6. return success (no internal ids).

Safeguards: opaque token (rotatable), closed-by-default window, dedupe, rate-limit, honeypot,
captcha. The endpoint can **only** create a participant for that token's session — nothing else.

---

## 5. Frontend

### Officer (authenticated, `openimis-fe-training_js`)
- **Sessions panel** in the training detail: add/edit Day 1, Day 2…
- Per session row: **"Attendance QR"** → dialog rendering the QR for
  `…/front/training/checkin/<session_token>`, an **Open/Close registration** toggle, a live
  check-in count, and copy-link / print / fullscreen (projector).
- QR generated client-side (`qrcode.react`).
- Attendance searcher gains a **session filter**.
- New right `2108xx` (manage session/QR).

### Attendee (PUBLIC, unauthenticated route)
- `…/front/training/checkin/:token` — registered via fe-core's
  `UNAUTHENTICATED_ROUTER_CONTRIBUTION_KEY` (same mechanism as `/login`, `/forgot_password`).
- Branded mobile form (the 6 fields + captcha) → "You're checked in" success state. **No login.**

---

## 6. Build phases

1. **BE** — `TrainingSession` model + `TrainingParticipant` fields + migration.
2. **BE** — session CRUD service/mutations/schema + public token-scoped check-in REST endpoint.
3. **FE officer** — Sessions panel + QR dialog (+ `qrcode.react`) + searcher session filter.
4. **FE public** — unauthenticated check-in page.
5. i18n, rebuild/sync dists, verify.

## 7. Notes / open follow-ups
- Captcha: lightweight built-in (honeypot + math / Cloudflare-Turnstile-style) since no paid
  service; can swap to a provider later.
- If single-day trainings are common, the officer UI can auto-create a default "Day 1" session so
  the QR is one click.
- Per-session model leaves room to later add session-level evidence or trainer assignment.

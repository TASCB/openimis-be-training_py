# 10 — User Manual (Training Management)

A task‑oriented guide for end users. For concepts see
[MODULE_OVERVIEW.md](MODULE_OVERVIEW.md); for problems see
[11-troubleshooting.md](11-troubleshooting.md).

## 1. Before you start

- You need the relevant **rights** on your role. The *IMIS Administrator* role has all
  training rights by default. If menus or the **Save** button are missing/disabled,
  see Troubleshooting → *"I can't see the menu / can't save"*.
- **Rights are read at login.** If rights were just granted, **log out and back in**.

## 2. Menus & pages

| Page | What it's for |
|---|---|
| **Trainings** | Search/list trainings; open or create one |
| **Training** (detail) | Create/edit a training + its assignments, participants, files |
| **Trainers** | Manage reusable trainer profiles |
| **Calendar** | Month/week view of scheduled trainings |
| **Attendance** | Searchable list of all participants/attendance across trainings, with filters |
| **Dashboard** | Summary counts by status and programme area |

### Attendance list

The **Attendance** page is a standard openIMIS searcher (Search Criteria panel + results
table). Filter by **Name**, **Attendance Status**, **Participant Type**, **Region /
District / Ward / Village**, and **Show Deleted**; each row links back to its training.
Attendance itself is recorded per training in the *Participants & Attendance* tab — this
page is the cross‑training read/report view.

## 3. Do I create a Trainer first? — No

You do **not** need a trainer to create a training. Recommended order:

1. **(Optional, once)** Create **Trainer Profiles** under *Trainers* for people you will
   assign repeatedly.
2. **Create the Training** — only **Code, Title, Start, End** are required. It saves as
   **Draft**.
3. **After saving**, the *Assignments*, *Participants* and *Materials/Evidence* panels
   appear. Add a trainer/staff assignment (to assign a registered trainer it must exist
   as a Trainer Profile first; otherwise assign an internal staff user).
4. **Advance the status** through the workflow as the training progresses.

## 4. Create a training (step by step)

1. Go to **Trainings → (＋) / New**.
2. Fill the header:
   - **Code*** — your training reference (must be unique).
   - **Title*** — name of the training.
   - **Programme Area** — pick the TASAF area it supports (Targeting, Payment, …).
     *This is the category, not the PAA.*
   - **Description** — free text.
   - **Start*** / **End*** — pick the **dates** (date‑only; End must be ≥ Start).
   - **Venue** — location/room name (used for venue conflict checks).
   - **Expected Participants** — a number.
   - **Location** — openIMIS location (Region/District/Ward/…).
   - **PAA** — the Productive Asset Area / programme operational area reference (free text).
   - **Status** — starts at **Draft** (read‑only; changes via workflow buttons).
3. Watch the **conflict banner**: a **red** banner = hard conflict (trainer/venue/staff
   already booked in that window) and **blocks saving**; a yellow banner is a soft
   warning only.
4. Click **Save**. The page reloads in edit mode with the child panels available.

> **Programme Area vs PAA.** *Programme Area* answers "what kind of training is this?"
> (a fixed list). *PAA* answers "which operational area/asset does it relate to?" (typed
> reference). Set both if relevant; neither is mandatory.

## 5. Assign trainers / staff

In the open training's **Assignments** panel:

1. Pick a **Trainer** (from Trainer Profiles) or assign an internal staff user.
2. Choose a **Role** (Lead Trainer, Facilitator, …) and **Status** (Assigned, Confirmed…).
3. Add notes if needed and save the row.

An assignment must have **a trainer or a staff member**. Active assignments
(Assigned/Confirmed) feed the trainer/staff conflict checks.

## 6. Participants & attendance

In the **Participants** panel add each participant (name, type, organization, etc.) and
set their **attendance status** (Invited → Confirmed → Attended/Absent/Replaced).

## 7. Materials & evidence

- **Materials** — files used before/during the training (agenda, slides). Upload via the
  Materials panel.
- **Evidence** — post‑training proof (report, attendance sheet, photos…). Each evidence
  file has an **Evidence Type**.

Files are uploaded through the module's upload endpoints and listed with who uploaded
them and when.

## 8. Status workflow (what the buttons do)

| Current status | Available actions | Right needed |
|---|---|---|
| **Draft** | Submit, Cancel | Update |
| **Submitted** | Approve, Reject | Approve |
| **Rejected** | Revise (→ Draft) | Update |
| **Approved** | Schedule, Cancel | Update |
| **Scheduled** | Start, Cancel | Update |
| **Ongoing** | Complete, Cancel | Update |
| **Completed** | Close | Update |
| **Cancelled / Closed** | — (terminal) | — |

- You can only **edit header details** while the training is **Draft** or **Rejected**.
- **Scheduling re‑checks hard conflicts** and will refuse if a trainer/venue/staff clash
  exists at that time.
- **Rejecting** can capture a reason.

## 9. Search & filter

On the **Trainings** list you can filter by Code, Title, Status, **Programme Area**,
**Trainer**, **Start date from/to**, and **Location**. Results are sortable and paginated.

## 10. Calendar & dashboard

- **Calendar** — switch between **Month** and **Week**; events are coloured by status;
  click an event to open the training.
- **Dashboard** — totals (this week / upcoming / ongoing / completed / cancelled),
  active trainers, and breakdowns **by status** and **by programme area**.

## 11. Field quick‑reference

| Field | Required | Notes |
|---|---|---|
| Code | ✅ | Unique reference |
| Title | ✅ | — |
| Start / End | ✅ | Date‑only; End ≥ Start |
| Programme Area | — | `TrainingCategory` (seeded list) |
| PAA | — | Free‑text operational‑area reference |
| Location | — | openIMIS location |
| Venue | — | Used for venue conflict detection |
| Expected Participants | — | Whole number |
| Status | — | Managed by workflow buttons, not edited directly |

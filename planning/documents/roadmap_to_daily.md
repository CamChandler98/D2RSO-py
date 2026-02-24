# D2RSO Python — Solo Project Operating Playbook

## Purpose
This document is the source of truth for how I run planning and execution using two GitHub Project boards:
1. **Roadmap** (epic-level planning)
2. **Delivery** (task-level Kanban)

# Board Structure

## 1) Roadmap Board

**Name:** `D2RSO Python — Roadmap`  
**Level:** Epics/outcomes only (no implementation tasks)

### Status Columns
- `Now`
- `Next`
- `Later`
- `Done`

### Required Fields
- Priority: `P0`, `P1`, `P2`
- Estimate: `S`, `M`, `L`
- Milestone: `MVP`, `Parity`, `Release`, `Icebox`

---

## 2) Delivery Board
**Name:** `D2RSO Python — Delivery`  
**Level:** Implementation cards only

### Status Columns
- `Now`
- `Next`
- `Later`
- `Done`

### Required Fields
- Priority: `P0`, `P1`, `P2`
- Estimate: `S`, `M`, `L`
- Milestone: `MVP`, `Parity`, `Release`

### WIP Rule (Critical)
- Maximum **2** cards in `Now` at any time.

---

# Roadmap → Delivery Mapping
### Epic: MVP — Foundation & Architecture
- [x] Initialize Python app skeleton
- [x] Add dependency baseline

### Epic: MVP — Core Models & Persistence
- [ ] Implement domain models
- [ ] Build JSON settings store
- [ ] Implement key catalog + icon registry

### Epic: MVP — Tracker Engine
- [ ] Create normalized input event contract
- [ ] Implement timer orchestration service
- [ ] Add unit tests for sequence + timer lifecycle

### Epic: Parity — Overlay Window
- [ ] Build transparent overlay window
- [ ] Implement preview vs runtime click-through
- [ ] Implement red-overlay threshold behavior

### Epic: Parity — Input Capture Stack
- [ ] Add global keyboard adapter
- [ ] Add global mouse adapter
- [ ] Add gamepad adapter
- [ ] Integrate InputRouter start/stop

### Epic: Parity — Main App UI
- [ ] Build profiles CRUD UI
- [ ] Build skill rows UI
- [ ] Build play/stop + preview controls

### Epic: Release — UX & Desktop Behavior
- [ ] Port options dialog
- [ ] Add system tray integration
- [ ] Add single-instance lock

### Epic: Release — Packaging & CI
- [ ] Create PyInstaller packaging
- [ ] Add CI pipeline

### Epic: Release — Docs & Onboarding
- [ ] Write contributor docs

---

## Weekly Planning Ritual (30 minutes)

## Step 1: Pick one active epic
- Move exactly one Roadmap epic to `Now`.
- Keep all other epics in `Next` or `Later`.

## Step 2: Pull tasks into Delivery `Now`
- Pull 1–2 cards mapped to that epic into `Now`.
- Do not pull tasks from other epics unless blocked.

## Step 3: Define weekly finish line
- Write a short weekly goal:
  - _Example: “Finish MVP Tracker Engine core + tests.”_

## Step 4: Review risk
- Mark blockers on cards immediately.
- If blocked > 1 day, either split or switch to next card in same epic.

---

## Daily Operating Rules (10 minutes)

- [ ] Check Delivery `Now` cards first.
- [ ] Move finished cards to `Done` same day.
- [ ] Keep `Now` at 1–2 cards max.
- [ ] If a card is too big, split it before continuing.
- [ ] Add short progress note on long-running cards.

---

## Definition of Ready (DoR) for Delivery cards
A card can enter `Now` only if:
- [ ] Objective is clear.
- [ ] Scope is bounded.
- [ ] Acceptance criteria are testable.
- [ ] No unknown hard blocker exists.

---

## Definition of Done (DoD) for Delivery cards
A card is `Done` only if:
- [ ] Code/work is complete.
- [ ] Tests/checks pass (as applicable).
- [ ] Basic docs/comments updated (if needed).
- [ ] Card notes include any follow-up tasks.

---

## Monthly Review (45 minutes)

- [ ] Close completed Roadmap epic(s).
- [ ] Re-prioritize `Next` epics.
- [ ] Move stale items from `Now`/`Next` back to `Later` if needed.
- [ ] Decide next month’s single active epic order.

---

## Lightweight Metrics (solo-friendly)

Track these once per week:
- **Throughput:** number of Delivery cards moved to `Done`
- **Cycle time:** average days from `Now` → `Done`
- **Blocked count:** number of cards blocked > 1 day
- **WIP violations:** number of times `Now` exceeded 2 cards

Use this to adjust scope, not to punish velocity.

---

## Card Templates

## Delivery Card Template
```md
## Objective
[Outcome]

## Scope
- [Task]
- [Task]
- [Task]

## Acceptance Criteria
- [ ] [Testable condition]
- [ ] [Testable condition]
- [ ] [Testable condition]

## Notes
- [Optional implementation notes]

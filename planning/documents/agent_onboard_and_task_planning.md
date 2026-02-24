# D2RSO Python Agent Onboarding & Task Planning Guide

## 1) Purpose of this document
This guide helps any AI agent quickly understand the project, your board workflow, and exactly how to produce a high-quality **step-by-step implementation plan** for a card from your Delivery board.

Use this when handing off work to an agent so responses are consistent and execution-ready.

---

## 2) Project purpose (what we are building)
You are planning a Python implementation of the D2RSO timer overlay application.

Primary goals:
- Build a Windows-first desktop app that tracks timed skills.
- Capture global input (keyboard/mouse/gamepad).
- Show active cooldowns on a transparent overlay.
- Persist profiles/settings and support a practical solo-dev delivery flow.

Non-goals for early milestones:
- Perfect cross-platform support.
- Premature architecture complexity.
- Feature creep beyond Roadmap/Delivery cards.

---

## 3) Planning system source of truth
The project is managed with two boards:

1. **Roadmap Board** (`D2RSO Python — Roadmap`)
   - Epics/outcomes only.
   - Columns: `Now`, `Next`, `Later`, `Done`
   - Fields: Priority (`P0/P1/P2`), Estimate (`S/M/L`), Milestone (`MVP/Parity/Release/Icebox`)
   - https://github.com/users/CamChandler98/projects/2
2. **Delivery Board** (`D2RSO Python — Delivery`) 
   - Implementation tasks only.
   - Columns: `Now`, `Next`, `Later`, `Done`
   - Fields: Priority (`P0/P1/P2`), Estimate (`S/M/L`), Milestone (`MVP/Parity/Release`)
   - **WIP rule:** Max 2 cards in `Now`.
   - https://github.com/users/CamChandler98/projects/1
---

## 4) Epic-to-task map (context for planning)
- **MVP — Foundation & Architecture**
  - Initialize Python app skeleton
  - Add dependency baseline

- **MVP — Core Models & Persistence**
  - Implement domain models
  - Build JSON settings store
  - Implement key catalog + icon registry

- **MVP — Tracker Engine**
  - Create normalized input event contract
  - Implement timer orchestration service
  - Add unit tests for sequence + timer lifecycle

- **Parity — Overlay Window**
  - Build transparent overlay window
  - Implement preview vs runtime click-through
  - Implement red-overlay threshold behavior

- **Parity — Input Capture Stack**
  - Add global keyboard adapter
  - Add global mouse adapter
  - Add gamepad adapter
  - Integrate InputRouter start/stop

- **Parity — Main App UI**
  - Build profiles CRUD UI
  - Build skill rows UI
  - Build play/stop + preview controls

- **Release — UX & Desktop Behavior**
  - Port options dialog
  - Add system tray integration
  - Add single-instance lock

- **Release — Packaging & CI**
  - Create PyInstaller packaging
  - Add CI pipeline

- **Release — Docs & Onboarding**
  - Write contributor docs

---

## 5) What an agent should do when given a Delivery card
When assigned one card, the agent should produce a plan with this exact sequence:

1. **Restate the card** in plain language.
2. **Identify dependencies** (blocking cards, required decisions, tooling assumptions).
3. **Define implementation steps** (ordered, concrete, no hand-wavy phrasing).
4. **Define verification steps** (unit/integration/manual checks).
5. **List risks + mitigations**.
6. **Suggest scope split** if the task is too large for one focused work session.
7. **Provide a completion checklist** mapped to card acceptance criteria.

---

## 6) Required output format for agent responses
Ask the agent to use the following structure every time:

```md
## Task Summary
- Card: [title]
- Epic: [epic]
- Milestone: [MVP/Parity/Release]

## Assumptions
- [assumption]

## Dependencies / Prerequisites
- [dependency]

## Step-by-Step Implementation Plan
1. [step]
2. [step]
3. [step]

## Validation Plan
- Automated checks:
  - [test command]
- Manual checks:
  - [manual scenario]

## Risks & Mitigations
- Risk: [risk]
  - Mitigation: [mitigation]

## Suggested Task Split (if needed)
- Subtask A: [outcome]
- Subtask B: [outcome]

## Done Checklist
- [ ] [acceptance criterion 1]
- [ ] [acceptance criterion 2]
- [ ] [acceptance criterion 3]
```

---

## 7) Prompt template to give any agent
Copy/paste this message and replace bracketed values:

```md
You are helping with the D2RSO Python project.

Project context:
- Two-board system:
  - Roadmap board = epics
  - Delivery board = implementation tasks
- WIP limit on Delivery `Now` = 2
- Current active epic: [EPIC NAME]

Task card to plan:
- Title: [CARD TITLE]
- Status: [Now/Next/Later]
- Priority: [P0/P1/P2]
- Estimate: [S/M/L]
- Milestone: [MVP/Parity/Release]
- Objective: [OBJECTIVE]
- Scope:
  - [SCOPE ITEM]
  - [SCOPE ITEM]
- Acceptance Criteria:
  - [CRITERION]
  - [CRITERION]

Please provide a detailed, implementation-ready step-by-step plan using this exact structure:
1) Task Summary
2) Assumptions
3) Dependencies / Prerequisites
4) Step-by-Step Implementation Plan
5) Validation Plan (automated + manual)
6) Risks & Mitigations
7) Suggested Task Split (if needed)
8) Done Checklist

Constraints:
- Keep scope tightly aligned to this card only.
- Call out any blocker explicitly.
- If scope seems too large, propose a split before implementation.
```

---

## 8) Quality bar for an acceptable agent plan
A plan is acceptable only if it is:
- **Specific:** names concrete files/components/services to touch.
- **Sequential:** clearly ordered from setup to validation.
- **Testable:** includes explicit checks and expected outcomes.
- **Scoped:** does not silently include unrelated features.
- **Actionable:** a developer can execute it without follow-up clarification.

Reject or revise plans that are generic, skip validation, or ignore dependencies.

---

## 9) Fast review checklist (for you)
Before accepting an agent plan, check:
- [ ] Does it map directly to card objective/scope?
- [ ] Are dependencies identified early?
- [ ] Are steps concrete and in implementation order?
- [ ] Is there a real validation plan (not vague “test it”)?
- [ ] Are risks and fallback paths included?
- [ ] Is there a clear Done checklist?

---

## 10) Example: quick filled prompt
```md
Current active epic: MVP — Tracker Engine

Task card to plan:
- Title: Implement timer orchestration service
- Status: Now
- Priority: P0
- Estimate: M
- Milestone: MVP
- Objective: Drive countdown lifecycle independent of UI.
- Scope:
  - Start/restart/remove active timers by skill ID.
  - Emit updates for remaining time and completion.
  - Prevent duplicate active trackers for same skill.
- Acceptance Criteria:
  - Re-trigger refreshes existing timer.
  - Completion emits removal event.
  - Service is testable without GUI thread.
```

Use this guide as the standard whenever delegating a Delivery card to an agent.

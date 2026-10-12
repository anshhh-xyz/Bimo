# Roadmap: Cross-Client Memory & Handoff System

A shared project-state layer that works across multiple Claude web accounts and Claude Code, with reliable change tracking, provenance, conflict detection and handoffs.

**Stack:** FastAPI + PostgreSQL + remote MCP server + GitHub webhooks + Claude Code hooks

**Success criteria (from planning.md):**
- Cross-account continuity: one account records a decision, another retrieves it correctly.
- Cross-surface continuity: same state works from Claude web and Claude Code.
- Reliable handoff: next account can see unfinished work and tell committed from uncommitted/unverified work.

---

## Phase 0: Decisions and setup
**Goal:** Lock the choices that are painful to change later.

- [ ] 0.1 Create the GitHub repo and folder structure (`backend/`, `docs/`, `tests/`)
- [ ] 0.2 Set up Python env (3.11+), dependencies, `.env` handling
- [ ] 0.3 Choose hosting (local + tunnel for dev, then a free-tier host)
- [ ] 0.4 Decide identity model: how the 3 Claude accounts map to users, and how users map to projects
- [ ] 0.5 Write a one-page architecture note (one deployable service, MCP as a thin adapter over FastAPI logic)

**Done when:** repo exists, env runs `hello world` FastAPI, identity model is written down.

---

## Phase 1: Database and schema
**Goal:** Persistent, append-only foundation.

- [ ] 1.1 Install PostgreSQL (local or hosted), connect with SQLAlchemy + Alembic migrations
- [ ] 1.2 Tables: `users`, `projects`, `project_members`
- [ ] 1.3 Table: `events` (append-only: id, project_id, user_id, surface, type, payload, created_at)
- [ ] 1.4 Tables: `tasks`, `decisions`, `handoffs` (each with `version` and provenance status columns)
- [ ] 1.5 Seed script with 3 test users and 1 test project

**Done when:** migrations run cleanly and seed data is queryable.

---

## Phase 2: Core backend logic (FastAPI)
**Goal:** All memory and project logic works over plain HTTP before MCP is involved.

- [ ] 2.1 Auth and permission checks (user must be a project member)
- [ ] 2.2 Endpoints: get project state, create/update task, record decision, list changes
- [ ] 2.3 Optimistic concurrency: updates carry a `version`; stale writes return a conflict error
- [ ] 2.4 Provenance model: each fact is `verified`, `asserted` or `unverified`, with source (account, surface, commit SHA)
- [ ] 2.5 Handoff schema + endpoint: current state, completed, blockers, open questions, files touched, last commit SHA, verification status, next action
- [ ] 2.6 Unit tests for each of the above

**Done when:** you can run the full flow with curl or pytest, including a deliberate conflict.

---

## Phase 3: MCP server layer
**Goal:** Expose the backend as tools Claude can call.

- [ ] 3.1 Add an MCP server (Python MCP SDK) inside the same service
- [ ] 3.2 Tools: `get_project_state`, `record_decision`, `update_task`, `save_handoff`, `list_changes`
- [ ] 3.3 Return memory as clearly delimited data (guard against prompt injection from stored content)
- [ ] 3.4 Remote transport (streamable HTTP) reachable over HTTPS
- [ ] 3.5 OAuth flow so each Claude account authenticates as its own user
- [ ] 3.6 Test locally with an MCP inspector before touching Claude

**Done when:** the inspector can authenticate and call every tool.

---

## Phase 4: Connect clients and test continuity
**Goal:** Prove the core value on real clients.

- [ ] 4.1 Claude web: add the custom connector in Account A, enable it in a chat
- [ ] 4.2 Repeat for Accounts B and C (test each independently)
- [ ] 4.3 Claude Code: add the remote MCP server and test separately
- [ ] 4.4 Scenario test: A records a decision, B retrieves it
- [ ] 4.5 Scenario test: web saves a handoff, Claude Code picks it up
- [ ] 4.6 Add project instructions telling Claude to fetch state at start and save a handoff at end

**Done when:** both continuity criteria pass on real clients.

---

## Phase 5: Automatic change tracking
**Goal:** Track changes without relying on Claude to remember to report them.

- [ ] 5.1 GitHub webhook endpoint (verify signature) for pushes and PRs, stored as `verified` events
- [ ] 5.2 Claude Code hooks (session end, after edits) that post `git status` / diff summary
- [ ] 5.3 Label local reports as self-reported; track three states: pushed, committed locally, uncommitted
- [ ] 5.4 Link commit SHAs to tasks and handoffs

**Done when:** a commit and an uncommitted edit both appear in `list_changes` with correct status.

---

## Phase 6: Conflict detection and verification
**Goal:** Surface contradictions instead of hiding them.

- [ ] 6.1 Detect two accounts editing the same task/record concurrently
- [ ] 6.2 Detect contradictory decisions on the same topic
- [ ] 6.3 Add a `conflicts` view/tool and a resolve action
- [ ] 6.4 Verification workflow: mark an asserted fact as verified (with who and when)
- [ ] 6.5 Handoff output highlights unverified items and open conflicts

**Done when:** a staged contradiction between two accounts shows up in the next handoff.

---

## Phase 7: Hardening, docs and demo
**Goal:** Make it presentable and trustworthy.

- [ ] 7.1 Test suite for the full scenarios (cross-account, cross-surface, conflict, handoff)
- [ ] 7.2 Rate limiting, input validation, secrets handling, no secrets stored in memory
- [ ] 7.3 Deploy to hosting with HTTPS
- [ ] 7.4 README with architecture diagram (GitHub as inbound webhooks, local filesystem path via Claude Code)
- [ ] 7.5 Demo script or short recording showing the three scenarios end to end

**Done when:** a stranger can set it up from the README and reproduce the demo.

---

## Working rhythm
One step at a time. Finish a step, tell me the result (or paste any error), and we move to the next. Tick the boxes as you go.

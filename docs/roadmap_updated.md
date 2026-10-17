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

- [✔] 0.1 Create the GitHub repo and folder structure (`backend/`, `docs/`, `tests/`)
- [✔] 0.2 Set up Python env (3.11+), dependencies, `.env` handling
- [✔] 0.3 Choose hosting (local + tunnel for dev, then a free-tier host)
- [✔] 0.4 Decide identity model: how the 3 Claude accounts map to users, and how users map to projects
- [✔] 0.5 Write a one-page architecture note (one deployable service, MCP as a thin adapter over FastAPI logic)

**Done when:** repo exists, env runs `hello world` FastAPI, identity model is written down.

---

## Phase 1: Database and schema
**Goal:** Persistent, append-only foundation.

- [✔] 1.1 Install PostgreSQL (local or hosted), connect with SQLAlchemy + Alembic migrations
- [✔] 1.2 Tables: `users`, `projects`, `project_members`
- [✔] 1.3 Table: `events` (append-only: id, project_id, user_id, surface, type, payload, created_at)
- [✔] 1.4 Tables: `tasks`, `decisions`, `handoffs` (each with `version` and provenance status columns)
- [✔] 1.5 Seed script with 3 test users and 1 test project

**Done when:** migrations run cleanly and seed data is queryable.

---

## Phase 2: Core backend logic (FastAPI)
**Goal:** All memory and project logic works over plain HTTP before MCP is involved.

- [✔] 2.1 Auth and permission checks (user must be a project member)
- [✔] 2.2 Endpoints: get project state, create/update task, record decision, list changes
- [✔] 2.3 Optimistic concurrency: updates carry a `version`; stale writes return a conflict error
- [✔] 2.4 Provenance model: each fact is `verified`, `asserted` or `unverified`, with source (account, surface, commit SHA)
- [✔] 2.5 Handoff schema + endpoint: current state, completed, blockers, open questions, files touched, last commit SHA, verification status, next action
- [✔] 2.6 Unit tests for each of the above

**Done when:** you can run the full flow with curl or pytest, including a deliberate conflict.

---

## Phase 3: MCP server layer
**Goal:** Expose the backend as tools Claude can call.

- [✔] 3.1 Add an MCP server (Python MCP SDK) inside the same service
- [✔] 3.2 Tools: `get_project_state`, `record_decision`, `update_task`, `save_handoff`, `list_changes`
- [✔] 3.3 Return memory as clearly delimited data (guard against prompt injection from stored content)
- [✔] 3.4 Remote transport (streamable HTTP) reachable over HTTPS
- [✔] 3.5 OAuth flow so each Claude account authenticates as its own user
- [✔] 3.6 Test locally with an MCP inspector before touching Claude

**Done when:** the inspector can authenticate and call every tool.

---

## Phase 4: Project membership and access management
**Goal:** Let project owners explicitly grant, limit and revoke access for individual Bimo users to a project.Overall to implement project accesss management to a ai agent/user.

- [✔] 4.1 Define the membership rules: `viewer`, `member`/`editor`, and `owner`; document exactly what each role can do
- [✔] 4.2 Add a way to list a project's members, including their email/identity and role
- [✔] 4.3 Add an owner-authorized endpoint to add an existing Bimo user to a project by email and assign a role
- [✔] 4.4 Add an owner-authorized endpoint to remove a user from a project
- [✔] 4.5 Add an owner-authorized endpoint to change a member's role
- [✔] 4.6 Enforce authorization on membership-management endpoints; non-owners must not be able to grant access or change roles
- [✔] 4.7 Protect ownership: prevent removing or demoting the last owner; define whether owners can remove themselves
- [✔] 4.8 Validate that adding an unknown email returns a clear error; do not silently create an account unless an explicit registration/invitation flow is implemented
- [✔] 4.9 Ensure every project-specific REST and MCP tool checks membership and the required role before returning or modifying data
- [✔] 4.10 Test access boundaries: a user can access projects they belong to, cannot access projects they are not a member of, and loses access after removal
- [✔] 4.11 Test role boundaries for read, write and membership-management operations
- [✔] 4.12 Document that the OAuth email/passphrase authenticates a Bimo user, while `project_members` determines which projects that user can access

**Done when:** an owner can add, remove and change a member's role; separate Bimo users receive only the project access explicitly granted to them; unauthorized requests are rejected and covered by tests.

---

## Phase 5: Connect clients and test continuity
**Goal:** Prove the core value on real clients after project permissions are manageable.

- [x] 5.1 Claude web: add the custom connector in Account A, enable it in a chat
- [x] 5.2 Repeat for Accounts B and C, authenticating each with its own Bimo user credentials
- [ ] 5.3 Configure membership so only the intended accounts can access each test project
- [ ] 5.4 Claude Code: add the remote MCP server and test separately (deferred: not installed; ChatGPT web tested as a second client instead)
- [ ] 5.5 Scenario test: A records a decision, B retrieves it when both have project access
- [ ] 5.6 Scenario test: C is denied access to a project it has not been added to
- [ ] 5.7 Scenario test: remove B from a project and confirm subsequent requests are denied
- [ ] 5.8 Scenario test: web saves a handoff, Claude Code picks it up when authenticated as a user with access
- [ ] 5.9 Add project instructions telling Claude to fetch state at start and save a handoff at end

**Done when:** project membership boundaries and cross-account/cross-surface continuity pass on real clients.

---

## Phase 6: Automatic change tracking
**Goal:** Track changes without relying on Claude to remember to report them.

- [ ] 6.1 GitHub webhook endpoint (verify signature) for pushes and PRs, stored as `verified` events
- [ ] 6.2 Claude Code hooks (session end, after edits) that post `git status` / diff summary
- [ ] 6.3 Label local reports as self-reported; track three states: pushed, committed locally, uncommitted
- [ ] 6.4 Link commit SHAs to tasks and handoffs

**Done when:** a commit and an uncommitted edit both appear in `list_changes` with correct status.

---

## Phase 7: Conflict detection and verification
**Goal:** Surface contradictions instead of hiding them.

- [ ] 7.1 Detect two accounts editing the same task/record concurrently
- [ ] 7.2 Detect contradictory decisions on the same topic
- [ ] 7.3 Add a `conflicts` view/tool and a resolve action
- [ ] 7.4 Verification workflow: mark an asserted fact as verified (with who and when)
- [ ] 7.5 Handoff output highlights unverified items and open conflicts

**Done when:** a staged contradiction between two accounts shows up in the next handoff.

---

## Phase 8: Hardening, docs and demo
**Goal:** Make it presentable and trustworthy.

- [ ] 8.1 Test suite for the full scenarios (cross-account, cross-surface, conflict, handoff, access control)
- [ ] 8.2 Rate limiting, input validation, secrets handling, no secrets stored in memory
- [ ] 8.3 Deploy to hosting with HTTPS
- [ ] 8.4 README with architecture diagram (GitHub as inbound webhooks, local filesystem path via Claude Code)
- [ ] 8.5 Demo script or short recording showing the scenarios end to end, including a denied-access case

**Done when:** a stranger can set it up from the README and reproduce the demo, including project-level access restrictions.

---

## Working rhythm
One step at a time. Finish a step, tell me the result (or paste any error), and we move to the next. Tick the boxes as you go.

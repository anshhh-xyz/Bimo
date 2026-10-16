# Bimo

**A shared project-state layer for AI coding agents.** Bimo gives multiple Claude web accounts and Claude Code one common, persistent memory of a project: what was decided, what is done, what is blocked, and what to do next. It tracks who changed what, separates verified facts from assumptions, and produces clean handoffs between accounts and tools.

> **Status:** Work in progress. The backend, database and MCP server work locally; client continuity testing, automatic change tracking and conflict detection are in progress. See [Roadmap](#roadmap).

---

## Table of contents

- [The problem](#the-problem)
- [What Bimo does](#what-bimo-does)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Data model](#data-model)
- [MCP tools](#mcp-tools)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Connecting Claude](#connecting-claude)
- [Testing](#testing)
- [Design decisions](#design-decisions)
- [Roadmap](#roadmap)
- [Security notes](#security-notes)
- [License](#license)

---

## The problem

When you work on one project across several Claude accounts, or across Claude on the web and Claude Code, each session starts from zero. Context lives in separate chats, one account's assumptions get mistaken for facts, two accounts can silently contradict each other, and nobody can tell which changes were actually committed.

Sharing memory is not the same as synchronizing every change. Bimo treats this as a small distributed-systems problem: it needs a single source of truth, explicit provenance, and conflict handling.

## What Bimo does

1. **Cross-session change tracking.** Records what changed, which account made the change, which files were affected, whether the work was committed, and what still needs verification.
2. **Project-aware handoffs.** The next account receives current state, completed work, blockers, open questions, files touched, last commit SHA, verification status and a next action, not just a pile of notes.
3. **Provenance and conflict detection.** Every fact is labelled `verified`, `asserted` or `unverified`, with its source (account, surface, commit SHA). Concurrent edits and contradictory decisions are surfaced instead of hidden.
4. **One memory layer across clients.** The same project state is reachable from Claude web, Claude Code, and later any MCP-compatible agent.

### Success criteria

- **Cross-account continuity:** one account records a decision and another retrieves it correctly.
- **Cross-surface continuity:** the same information works from Claude web and Claude Code.
- **Reliable handoff:** the next account can identify unfinished work and distinguish committed changes from uncommitted or unverified work.

## Architecture

Four distinct responsibilities:

| Layer | Responsibility |
|---|---|
| **Claude clients** (web, Claude Code) | Request information and submit updates |
| **MCP server** | Exposes the backend's capabilities as tools Claude can call |
| **FastAPI** | Enforces permissions and implements the memory and project logic |
| **PostgreSQL** | Stores the shared information persistently |

```
 Claude web (Account A, B, C)      Claude Code
            \                         /
             \     remote MCP (HTTPS) /
              v                      v
            +---------------------------+
            |   MCP adapter (thin)      |
            +-------------+-------------+
                          |
            +-------------v-------------+
            |  FastAPI: auth, project   |
            |  logic, versioning        |
            +-------------+-------------+
                          |
            +-------------v-------------+
            |  PostgreSQL (append-only  |
            |  events + current state)  |
            +---------------------------+
                          ^
          GitHub webhooks / Claude Code hooks   (planned)
```

The MCP layer is deliberately a thin adapter over the FastAPI logic, so everything can be tested over plain HTTP before any Claude client is involved. It ships as one deployable service.

## Tech stack

- **Python 3.11+**
- **FastAPI** + **Uvicorn** for the API
- **Pydantic v2** for validation
- **PostgreSQL** with **SQLAlchemy 2** and **Alembic** migrations (`psycopg` 3 driver)
- **MCP Python SDK** (`mcp`) with streamable HTTP transport
- **OAuth-style login** so each Claude account authenticates as its own Bimo user
- **pytest** + **httpx** for tests
- **ngrok** (or a Cloudflare tunnel) to expose the local server over HTTPS during development

## Data model

Seven tables:

| Table | Purpose |
|---|---|
| `users` | Bimo users; each Claude account maps to one |
| `projects` | Projects whose state is shared |
| `project_members` | Which users belong to which projects, with a permission role |
| `events` | Append-only log: `id, project_id, user_id, surface, type, payload, created_at` |
| `tasks` | Work items, with a `version` and provenance status |
| `decisions` | Recorded decisions, with a `version` and provenance status |
| `handoffs` | Structured end-of-session summaries |

Key ideas:

- **Append-only events** give a reliable audit trail of what happened and where (web vs Claude Code).
- **Optimistic concurrency.** Updates carry a `version`; a stale write returns a conflict error instead of overwriting.
- **Provenance.** Records note the agent or model that produced them (for example, Claude writes code, another model reviews it) and whether the claim is `verified`, `asserted` or `unverified`.

## MCP tools

| Tool | What it does |
|---|---|
| `get_project_state` | Returns current tasks, decisions, latest handoff and open items for a project |
| `record_decision` | Stores a decision with its provenance |
| `update_task` | Creates or updates a task (version-checked) |
| `save_handoff` | Saves a structured handoff for the next session or account |
| `list_changes` | Lists recent tracked changes for a project |

Stored content is returned as clearly delimited data so that text saved in memory cannot act as instructions to the model (prompt-injection guard).

## Project structure

```
Bimo/
├── backend/            # FastAPI app, models, migrations, MCP server, tests
├── docs/               # Planning notes and roadmap
├── requirements.txt    # Python dependencies
└── .gitignore
```

<!-- TODO: expand the backend/ tree (app, models, routers, mcp, alembic, tests) with your real file names. -->

## Getting started

### Prerequisites

- Python 3.11+
- PostgreSQL (local or hosted)
- ngrok or a Cloudflare tunnel (only needed to connect Claude web)

### 1. Clone and install

```bash
git clone https://github.com/anshhh-xyz/Bimo.git
cd Bimo
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Create the database

```bash
createdb memory
```

### 3. Configure environment variables

Create a `.env` file (never commit it):

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@localhost:5432/memory
# Add your OAuth/session secrets and any other settings used by the app
```

<!-- TODO: list the exact variable names your code reads. -->

### 4. Run migrations and seed test data

```bash
alembic upgrade head
python <path-to-seed-script>   # creates 3 test users and 1 test project
```

### 5. Start the server

```bash
uvicorn <module>:app --reload
```

<!-- TODO: replace <module> with your real import path, e.g. backend.main -->

Open `http://127.0.0.1:8000/docs` for the interactive API docs.

## Connecting Claude

Claude web and Claude Code have different connector setups. Test each client on its own, and do not assume that connecting one account connects the others.

### Expose the server over HTTPS

Claude connects to a remote MCP server, so your local service needs a public HTTPS URL:

```bash
ngrok http 8000
```

A reserved ngrok domain keeps the connector URL stable. A Cloudflare quick tunnel works too, but its URL changes every run.

### Claude web

In each Claude account:

1. Go to **Settings → Connectors**.
2. Choose **Add custom connector** and enter your MCP server URL.
3. Complete authentication, signing in as that account's own Bimo user.
4. Open a chat and enable the connector from the tools menu.
5. Ask Claude to get the project state or save a handoff.

### Claude Code

Add the same remote MCP server in Claude Code and test it separately.

### Recommended project instructions

Add this to your Claude project instructions so sessions stay in sync:

> At the start of a session, call `get_project_state`. At the end, call `save_handoff` with what was completed, what is blocked, and the next action.

## Testing

```bash
pytest
```

The suite covers the core logic over plain HTTP (including deliberate version conflicts) before MCP is involved. Planned scenario tests:

- Account A records a decision; Account B retrieves it.
- Web saves a handoff; Claude Code picks it up.
- A user without membership is denied access to a project.
- A removed member loses access.

## Design decisions

- **One service, thin MCP adapter.** All logic lives in FastAPI so it is testable without Claude.
- **Append-only events.** History is never rewritten, which makes handoffs and audits trustworthy.
- **Optimistic concurrency over locks.** Stale writes fail loudly with a conflict instead of silently clobbering data.
- **Provenance as a first-class field.** An account's assumption is not the same as a verified fact.
- **SQLAlchemy and Alembic.** Typed models and versioned schema migrations.
- **Authentication is separate from authorization.** OAuth proves *which Bimo user* you are; `project_members` decides *which projects* that user can access.

## Roadmap

- [x] **Phase 0:** Repo, environment, identity model
- [x] **Phase 1:** PostgreSQL schema, Alembic migrations, seed script
- [x] **Phase 2:** FastAPI logic: permissions, tasks, decisions, versioning, provenance, handoffs, tests
- [x] **Phase 3:** MCP server with streamable HTTP, working on Claude web through a tunnel
- [ ] **Phase 4:** Connect all accounts and Claude Code, run continuity scenarios, stable public URL
- [ ] **Phase 5:** Dynamic member management (add, remove and change roles through the API)
- [ ] **Phase 6:** Automatic change tracking: GitHub webhooks (signature-verified) and Claude Code hooks, distinguishing pushed, committed-locally and uncommitted work
- [ ] **Phase 7:** Conflict detection, a `conflicts` view and a verification workflow
- [ ] **Phase 8:** Hardening (rate limiting, validation, secrets handling), hosted deployment, demo

Detailed planning lives in [`docs/`](docs/).

## Security notes

- Never commit `.env` or any secrets.
- Do not store secrets or credentials in project memory.
- Every project-specific REST endpoint and MCP tool must check membership and role before returning or changing data.
- Stored memory is treated as untrusted data when returned to a model.

## License

No license has been added yet. Add one (for example MIT) before accepting contributions.

## Author

Built by [anshhh-xyz](https://github.com/anshhh-xyz).

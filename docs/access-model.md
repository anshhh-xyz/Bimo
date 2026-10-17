# Access model

## Authentication vs authorization
- **Authentication** (OAuth email/passphrase) proves *which Bimo user* is calling.
- **Authorization** (`project_members`) decides *which projects* that user can touch, and with what role.
- Membership is checked against the database on every REST request and every MCP tool call. Nothing is cached, so removals take effect immediately.

## Roles
| Role   | Read | Write (tasks, decisions, handoffs) | Manage members |
|--------|------|------------------------------------|----------------|
| viewer | yes  | no                                 | no             |
| editor | yes  | yes                                | no             |
| owner  | yes  | yes                                | yes            |

Only these three roles exist. The database rejects anything else (`ck_project_members_role`); the old `member` role was migrated to `editor`.

## Rules
- Only owners can add, remove or re-role members.
- Adding requires an existing Bimo user's email. Unknown emails return 404; accounts are never created implicitly.
- The last owner cannot be removed or demoted. An owner may leave if another owner exists.
- Non-members get 403 on every project resource (existence of a project is not revealed).
- Membership changes are written to the `events` log (`member_added`, `member_removed`, `member_role_changed`).
- Any authenticated Bimo user can create a project (`POST /projects`, or the `create_project` MCP tool) and becomes its owner. The owner is taken from the authenticated identity, never from the request body.
- Project, owner membership and a `project_created` event are written in one transaction, so a project without an owner cannot exist.
## Audit trail
- Every event records `user_id`, `surface` and `agent`. `agent` is derived server-side from the OAuth client the account logged in with (`claude`, `claude-code`, `chatgpt`, or a slug of an unknown client's name), so it cannot be spoofed by the model. Writes made with a static dev token carry no agent.
- Records (tasks, decisions, handoffs) keep the agent string the client supplied, falling back to the server-derived one.

## Login protection
- `/authorize` locks an email after 5 failed passphrases in 15 minutes, and an IP after 20. While locked, even the correct passphrase is refused (HTTP 429). A successful login resets the email's counter.
- Counters are in process memory: they reset on restart and are per instance.

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

`member` is a legacy alias of `editor`.

## Rules
- Only owners can add, remove or re-role members.
- Adding requires an existing Bimo user's email. Unknown emails return 404; accounts are never created implicitly.
- The last owner cannot be removed or demoted. An owner may leave if another owner exists.
- Non-members get 403 on every project resource (existence of a project is not revealed).
- Membership changes are written to the `events` log (`member_added`, `member_removed`, `member_role_changed`).
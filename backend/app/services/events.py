from datetime import datetime
from sqlalchemy import select
from app.models import Event


def log_event(session, *, project_id, user_id, surface, type, payload, agent=None):
    session.add(Event(project_id=project_id, user_id=user_id, surface=surface,
                      agent=agent, type=type, payload=payload))


def list_changes(session, project_id: int, since: datetime | None = None,
                 limit: int = 50) -> list[Event]:
    limit = max(1, min(limit, 200))
    q = select(Event).where(Event.project_id == project_id)
    if since is not None:
        q = q.where(Event.created_at > since)
    q = q.order_by(Event.created_at.desc(), Event.id.desc()).limit(limit)
    return list(session.scalars(q).all())

"""list_changes is what Claude uses to implement “show changes since last handoff”.
For the initial MCP integration, we don’t need to filter by handoff — just "
 "by project and timestamp (and limit). The “last handoff” logic can be added "
 "later if needed. The Event model currently stores payload as JSONB,
 "so you can send any dict; the UI will need to know how to render it." """
from app.models import Event

def log_event(session, *, project_id, user_id, surface, type, payload):
    session.add(Event(project_id=project_id, user_id=user_id,
                      surface=surface, type=type, payload=payload))
from fastapi.param_functions import Depends
from fastapi import Header
from app.db import get_session
from app.services import access
from app.services.access import Ctx  # noqa: F401  (re-exported)


def require_member(min_role: str = "viewer"):
    def dependency(project_id: int,
                   x_user_id: int = Header(...),
                   x_surface: str = Header("web"),
                   session=Depends(get_session)) -> Ctx:
        return access.get_ctx(session, x_user_id, project_id, x_surface, min_role)
    return dependency
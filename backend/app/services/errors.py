class ServiceError(Exception):
    """Base for all domain errors. REST maps status_code to HTTP;
    MCP ignores the number and returns the message."""
    status_code = 400

    def __init__(self, message: str = ""):
        super().__init__(message)
        self.message = message or self.__class__.__name__


class Unauthorized(ServiceError):
    status_code = 401


class Forbidden(ServiceError):
    status_code = 403


class NotFound(ServiceError):
    status_code = 404


class InvalidInput(ServiceError):
    status_code = 422

class StateConflict(ServiceError):
    """409 for rule violations that are not version conflicts
    (already a member, last owner)."""
    status_code = 409


class ConflictError(ServiceError):
    status_code = 409

    def __init__(self, current: dict):
        super().__init__("Version conflict")
        self.current = current


"""Services currently raise FastAPI’s HTTPException, which MCP can’t use. 
Domain errors are transport-neutral: each adapter translates them in its own way."""
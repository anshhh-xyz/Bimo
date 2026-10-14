class ConflictError(Exception):
    def __init__(self, current: dict):
        self.current = current
from typing import Any


class DomainError(Exception):
    """Base domain error. `code` is the stable API error code (e.g. WORLD_NOT_FOUND)."""

    def __init__(self, code: str, message: str = "", details: Any = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.details = details


class NotFoundError(DomainError):
    """Resource missing (HTTP 404)."""


class ConflictError(DomainError):
    """Concurrent update / uniqueness conflict (HTTP 409)."""


class InvalidStateError(DomainError):
    """Operation not allowed in current state (HTTP 409)."""


class DomainValidationError(DomainError):
    """Business-rule validation failure (HTTP 422)."""

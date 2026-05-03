"""
Base domain exceptions.

All domain-specific exceptions inherit from DomainException,
allowing the API layer to catch and translate them into HTTP responses.
"""


class DomainException(Exception):
    """Base exception for all domain-layer errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(self.message)


class EntityNotFoundError(DomainException):
    """Raised when a requested entity does not exist."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_type} with id '{entity_id}' not found",
            code="NOT_FOUND",
        )


class ValidationError(DomainException):
    """Raised when input data fails domain validation rules."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR")


class ServiceUnavailableError(DomainException):
    """Raised when a required service (AI model, DB, etc.) is not ready."""

    def __init__(self, service_name: str) -> None:
        super().__init__(
            message=f"Service '{service_name}' is currently unavailable",
            code="SERVICE_UNAVAILABLE",
        )

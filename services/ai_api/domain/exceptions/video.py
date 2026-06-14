"""Video generation domain exceptions."""

from services.ai_api.domain.exceptions.base import DomainException


class VideoGenerationError(DomainException):
    """Raised when the video generation model fails during inference."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="VIDEO_GENERATION_ERROR")


class InvalidPromptError(DomainException):
    """Raised when the input prompt is invalid or unsafe."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Invalid prompt: {reason}",
            code="INVALID_PROMPT",
        )


class VideoModelNotLoadedError(DomainException):
    """Raised when the video generation model is not loaded in memory."""

    def __init__(self) -> None:
        super().__init__(
            message="Video generation model is not loaded. Please wait for initialization.",
            code="MODEL_NOT_LOADED",
        )

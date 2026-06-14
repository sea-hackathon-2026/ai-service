"""Text-to-Speech domain exceptions."""

from services.ai_api.domain.exceptions.base import DomainException


class TTSError(DomainException):
    """Raised when the TTS engine fails during synthesis."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="TTS_ERROR")


class UnsupportedLanguageError(DomainException):
    """Raised when the requested language is not supported by the TTS model."""

    def __init__(self, language: str) -> None:
        super().__init__(
            message=f"Language '{language}' is not supported by the current TTS model",
            code="UNSUPPORTED_LANGUAGE",
        )


class UnsupportedVoiceError(DomainException):
    """Raised when the requested voice ID is not available."""

    def __init__(self, voice_id: str) -> None:
        super().__init__(
            message=f"Voice '{voice_id}' is not available",
            code="UNSUPPORTED_VOICE",
        )


class TextTooLongError(DomainException):
    """Raised when the input text exceeds the maximum allowed length."""

    def __init__(self, length: int, max_length: int) -> None:
        super().__init__(
            message=f"Text length {length} exceeds maximum of {max_length} characters",
            code="TEXT_TOO_LONG",
        )

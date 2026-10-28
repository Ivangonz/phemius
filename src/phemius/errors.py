"""Errors that map to the standard API error shape `{detail, code, hint, errors}`."""


class PhemiusError(Exception):
    code = "error"
    status_code = 500

    def __init__(
        self, message: str, hint: str | None = None, field: str | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.field = field


class NotFoundError(PhemiusError):
    code = "not_found"
    status_code = 404


class InvalidInputError(PhemiusError):
    code = "invalid_input"
    status_code = 400


class ServiceUnavailableError(PhemiusError):
    code = "unavailable"
    status_code = 503


class ModelError(PhemiusError):
    """A script model provider failed."""

    code = "model_error"
    status_code = 502


class VoiceError(PhemiusError):
    """A voice engine failed."""

    code = "voice_error"
    status_code = 502

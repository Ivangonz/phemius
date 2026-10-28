"""Errors that map to the standard API error shape `{detail, code, hint, errors}`."""


class PhemiusError(Exception):
    code = "error"
    status_code = 500

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        field: str | None = None,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.field = field
        self.field_errors = field_errors or (
            {field: message} if field is not None else {}
        )


class NotFoundError(PhemiusError):
    code = "not_found"
    status_code = 404


class InvalidInputError(PhemiusError):
    code = "invalid_input"
    status_code = 400


class SettingLockedError(PhemiusError):
    """A setting is fixed by an environment variable and cannot be saved."""

    code = "setting_locked"
    status_code = 409


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

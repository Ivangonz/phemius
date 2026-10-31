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


class InvalidSettingError(PhemiusError):
    """A setting value is well-formed but not one this library offers."""

    code = "invalid_setting"
    status_code = 422


class InvalidBackupError(InvalidInputError):
    """An uploaded archive is not a backup this version of Phemius can restore."""

    code = "invalid_backup"


class SettingLockedError(PhemiusError):
    """A setting is fixed by an environment variable and cannot be saved."""

    code = "setting_locked"
    status_code = 409


class DuplicateSourceError(PhemiusError):
    """The same folder (or, later, repository or space) is already a source."""

    code = "duplicate_source"
    status_code = 409


class JobStateError(PhemiusError):
    """A job action does not apply to the job's current state."""

    code = "invalid_job_state"
    status_code = 409


class DocumentBusyError(PhemiusError):
    """A document cannot change while one of its jobs is running."""

    code = "document_busy"
    status_code = 409


class LibraryBusyError(PhemiusError):
    """A whole-library operation cannot run while jobs or another one are running."""

    code = "library_busy"
    status_code = 409


class VoiceDownloadConflictError(PhemiusError):
    """The engine has no voice downloads, or another voice is downloading."""

    code = "voice_download_conflict"
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


class SourceError(PhemiusError):
    """A source cannot be read: a missing folder, later an expired token."""

    code = "source_error"
    status_code = 502

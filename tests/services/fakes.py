import subprocess
from collections.abc import Callable
from pathlib import Path

FAKE_EXECUTABLE = "/usr/bin/ffmpeg"


class FakeFfmpeg:
    """Stands in for the ffmpeg binary: writes a small output file or fails."""

    def __init__(
        self,
        exit_code: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        error: Exception | None = None,
    ) -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.error = error
        self.calls: list[list[str]] = []

    def run(
        self, executable: str, arguments: list[str], timeout: float
    ) -> subprocess.CompletedProcess[bytes]:
        self.calls.append(arguments)
        if self.error is not None:
            raise self.error
        if arguments[0] != "-version":
            Path(arguments[-1]).write_bytes(b"compressed")
        return subprocess.CompletedProcess(
            [executable, *arguments], self.exit_code, self.stdout, self.stderr
        )


type UseFfmpeg = Callable[[FakeFfmpeg | None], FakeFfmpeg]

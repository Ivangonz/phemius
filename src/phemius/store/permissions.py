"""Owner-only permissions for the library: it holds saved API keys and documents.

Folders are created `0700` and the database `0600`. Both are created with that
mode rather than chmod-ed afterwards, so there is no window in which another
local user could open them. SQLite creates the `-wal` and `-shm` files with the
database file's mode, so they follow it.
"""

import os
import stat
from pathlib import Path

PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
_GROUP_AND_OTHER_BITS = 0o077


def create_private_dir(path: Path) -> None:
    """Create `path` owner-only. Missing parents get the default mode."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.mkdir(mode=PRIVATE_DIR_MODE, exist_ok=True)


def create_private_file(path: Path) -> None:
    """Create an empty owner-only file if `path` does not exist yet."""
    try:
        os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, PRIVATE_FILE_MODE))
    except FileExistsError:
        pass


def tighten_library_permissions(data_dir: Path, db_path: Path) -> list[Path]:
    """Remove group and other access from the library; return what changed.

    Only the data folder and the database files are changed. Anything below the
    data folder, such as `audio/`, is unreachable once the folder is `0700`, and
    a watched folder elsewhere belongs to the user and is never touched.
    """
    if os.name == "nt":
        return []
    candidates = {
        data_dir: PRIVATE_DIR_MODE,
        db_path: PRIVATE_FILE_MODE,
        Path(f"{db_path}-wal"): PRIVATE_FILE_MODE,
        Path(f"{db_path}-shm"): PRIVATE_FILE_MODE,
    }
    return [
        path for path, mode in candidates.items() if _remove_shared_access(path, mode)
    ]


def _remove_shared_access(path: Path, private_mode: int) -> bool:
    try:
        current_mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        return False
    if not current_mode & _GROUP_AND_OTHER_BITS:
        return False
    path.chmod(private_mode)
    return True

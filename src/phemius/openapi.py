"""Export the OpenAPI schema the frontend generates its API types from.

Usage: python -m phemius.openapi [output-file]   (stdout when omitted)
"""

import json
import sys
from pathlib import Path
from typing import Any

from phemius.app import create_app


def export_openapi() -> dict[str, Any]:
    return create_app().openapi()


def main(arguments: list[str] | None = None) -> None:
    arguments = sys.argv[1:] if arguments is None else arguments
    text = json.dumps(export_openapi(), indent=2, sort_keys=True) + "\n"
    if arguments:
        Path(arguments[0]).write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()

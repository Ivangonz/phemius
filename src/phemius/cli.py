"""Command line: `phemius serve` starts the server on the access mode's address."""

import argparse
import os
import sys
from pathlib import Path

import uvicorn

from phemius import __version__
from phemius.config import ENV_PREFIX, load_config
from phemius.errors import PhemiusError
from phemius.services.access import LOOPBACK_HOST, bind_options
from phemius.store.database import init_database

DEFAULT_PORT = 8000


def main(arguments: list[str] | None = None) -> None:
    options = _parser().parse_args(arguments)
    if options.data_dir is not None:
        # Before any config loads: the data folder holds the saved settings.
        os.environ[ENV_PREFIX + "DATA_DIR"] = str(
            options.data_dir.expanduser().absolute()
        )
    try:
        serve(port=options.port, host=options.host, is_reloading=options.reload)
    except PhemiusError as error:
        print(_error_text(error), file=sys.stderr)
        sys.exit(1)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phemius", description="Hear your docs.")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    serve_parser = commands.add_parser("serve", help="Run the Phemius server")
    serve_parser.add_argument(
        "--host",
        help="Address to listen on (default: from PHEMIUS_ACCESS_MODE). Local mode"
        " accepts only this computer's addresses.",
    )
    serve_parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"(default: {DEFAULT_PORT})"
    )
    serve_parser.add_argument(
        "--data-dir",
        type=Path,
        help="Library folder (default: PHEMIUS_DATA_DIR or ~/.phemius)",
    )
    serve_parser.add_argument(
        "--reload", action="store_true", help="Restart on code changes (development)"
    )
    return parser


def serve(port: int, host: str | None = None, is_reloading: bool = False) -> None:
    # The saved access mode lives in the library, so open it before binding.
    init_database(load_config().db_path)
    bind = bind_options(load_config().access_mode, host)
    uvicorn.run(
        "phemius.app:app",
        host=bind.host,
        port=port,
        reload=is_reloading,
        proxy_headers=bind.is_proxy_trusted,
        # The proxy runs on this computer, whatever address Phemius listens on.
        forwarded_allow_ips=LOOPBACK_HOST if bind.is_proxy_trusted else None,
        # uvicorn's access log prints query strings, which may hold a token.
        access_log=False,
    )


def _error_text(error: PhemiusError) -> str:
    hint = f"\nHint: {error.hint}" if error.hint else ""
    return f"phemius: {error.message}{hint}"

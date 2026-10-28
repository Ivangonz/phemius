"""Command line: `phemius serve` starts the server on the access mode's address."""

import argparse

import uvicorn

from phemius.config import load_config
from phemius.services.access import bind_options
from phemius.store.database import init_database

DEFAULT_PORT = 8000


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="phemius", description="Hear your docs.")
    commands = parser.add_subparsers(dest="command", required=True)
    serve_parser = commands.add_parser("serve", help="Run the Phemius server")
    serve_parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve_parser.add_argument(
        "--reload", action="store_true", help="Restart on code changes (development)"
    )
    options = parser.parse_args(arguments)
    serve(port=options.port, is_reloading=options.reload)


def serve(port: int, is_reloading: bool = False) -> None:
    # The saved access mode lives in the library, so open it before binding.
    init_database(load_config().db_path)
    bind = bind_options(load_config().access_mode)
    uvicorn.run(
        "phemius.app:app",
        host=bind.host,
        port=port,
        reload=is_reloading,
        proxy_headers=bind.is_proxy_trusted,
        forwarded_allow_ips=bind.host if bind.is_proxy_trusted else None,
        # uvicorn's access log prints query strings, which may hold a token.
        access_log=False,
    )

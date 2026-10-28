import json
from pathlib import Path

from phemius.openapi import export_openapi, main


def test_export_includes_api_routes_only() -> None:
    paths = export_openapi()["paths"]

    assert "/api/health" in paths
    assert all(path.startswith("/api/") for path in paths)


def test_main_writes_sorted_schema_to_the_given_file(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"

    main([str(output)])

    text = output.read_text()
    assert json.loads(text) == export_openapi()
    assert text == json.dumps(export_openapi(), indent=2, sort_keys=True) + "\n"

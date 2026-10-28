import shutil
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

from phemius.models.base import ScriptModelCheck
from phemius.services import checks
from phemius.services.checks import SetupCheck
from tests.models.fakes import FakeScriptModel, UseScriptModel
from tests.services.fakes import FakeFfmpeg, UseFfmpeg

FFMPEG_VERSION = b"ffmpeg version 7.1.1 Copyright (c) 2000-2025\n"
GIGABYTE = 1024**3


class UnreachableScriptModel(FakeScriptModel):
    def check(self) -> ScriptModelCheck:
        return ScriptModelCheck(
            is_reachable=False,
            model=self.model,
            error="Could not reach the provider.",
            hint="Check the base URL.",
        )


class HungScriptModel(FakeScriptModel):
    """A provider that never answers until the test releases it."""

    def __init__(self) -> None:
        super().__init__()
        self.release = threading.Event()

    def check(self) -> ScriptModelCheck:
        self.release.wait(timeout=10)
        return super().check()


class BrokenScriptModel(FakeScriptModel):
    def check(self) -> ScriptModelCheck:
        raise RuntimeError("unexpected")


@pytest.fixture(autouse=True)
def ready_environment(
    isolated_env: Path, use_ffmpeg: UseFfmpeg, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every check passes unless a test changes one condition."""
    isolated_env.mkdir(parents=True)
    use_ffmpeg(FakeFfmpeg(stdout=FFMPEG_VERSION))
    monkeypatch.setattr(checks, "running_python", lambda: (3, 12))
    monkeypatch.setattr(checks, "_last_run", None)


@pytest.fixture
def hung_model(use_script_model: UseScriptModel) -> Iterator[HungScriptModel]:
    model = HungScriptModel()
    use_script_model(model)
    yield model
    model.release.set()


def run_check(check_id: str) -> SetupCheck:
    return next(check for check in checks.run_checks().checks if check.id == check_id)


def test_runs_every_check_in_a_fixed_order(use_script_model: UseScriptModel) -> None:
    use_script_model(FakeScriptModel())

    run = checks.run_checks()

    assert [check.id for check in run.checks] == [
        "python",
        "script_model",
        "voice_engine",
        "library",
        "watch_folder",
        "ffmpeg",
    ]
    assert {check.status for check in run.checks} == {"ok", "optional"}


def test_python_in_kokoro_range_is_ok() -> None:
    assert run_check("python").status == "ok"


def test_python_outside_kokoro_range_needs_attention_with_kokoro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checks, "running_python", lambda: (3, 13))
    monkeypatch.setenv("PHEMIUS_TTS", "kokoro")

    check = run_check("python")

    assert check.status == "needs_attention"
    assert "3.13" in check.detail
    assert check.hint is not None


def test_python_outside_kokoro_range_is_optional_with_another_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(checks, "running_python", lambda: (3, 13))

    assert run_check("python").status == "optional"


def test_reachable_script_model_reports_latency(
    use_script_model: UseScriptModel,
) -> None:
    use_script_model(FakeScriptModel())

    check = run_check("script_model")

    assert check.status == "ok"
    assert "fake/model" in check.detail
    assert "ms" in check.detail


def test_unreachable_script_model_needs_attention(
    use_script_model: UseScriptModel,
) -> None:
    use_script_model(UnreachableScriptModel())

    check = run_check("script_model")

    assert (check.status, check.hint) == ("needs_attention", "Check the base URL.")
    assert "Could not reach the provider." in check.detail


def test_script_model_that_cannot_be_built_needs_attention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_PROVIDER", "openrouter")

    check = run_check("script_model")

    assert check.status == "needs_attention"
    assert check.hint is not None


def test_offline_script_rules_are_optional() -> None:
    check = run_check("script_model")

    assert check.status == "optional"
    assert check.hint is not None


def test_ready_voice_engine_is_ok() -> None:
    assert run_check("voice_engine").status == "ok"


def test_unknown_voice_engine_needs_attention(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_TTS", "nope")

    check = run_check("voice_engine")

    assert check.status == "needs_attention"
    assert check.hint is not None


def test_library_with_free_space_is_ok() -> None:
    check = run_check("library")

    assert check.status == "ok"
    assert "free" in check.detail


def test_library_low_on_space_needs_attention(monkeypatch: pytest.MonkeyPatch) -> None:
    low = SimpleNamespace(total=10 * GIGABYTE, used=0, free=GIGABYTE // 2)
    monkeypatch.setattr(shutil, "disk_usage", lambda path: low)

    check = run_check("library")

    assert check.status == "needs_attention"
    assert "0.5 GB free" in check.detail


def test_unwritable_library_needs_attention(
    isolated_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_DATA_DIR", str(isolated_env / "missing"))

    check = run_check("library")

    assert check.status == "needs_attention"
    assert check.hint is not None


def test_unconfigured_watch_folder_is_optional() -> None:
    assert run_check("watch_folder").status == "optional"


def test_readable_watch_folder_is_ok(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_WATCH_DIR", str(tmp_path))

    assert run_check("watch_folder").status == "ok"


def test_missing_watch_folder_needs_attention(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_WATCH_DIR", str(tmp_path / "missing"))

    check = run_check("watch_folder")

    assert check.status == "needs_attention"
    assert check.hint is not None


def test_installed_ffmpeg_is_ok() -> None:
    check = run_check("ffmpeg")

    assert check.status == "ok"
    assert "7.1.1" in check.detail


def test_missing_ffmpeg_is_optional_for_wav(use_ffmpeg: UseFfmpeg) -> None:
    use_ffmpeg(None)

    check = run_check("ffmpeg")

    assert check.status == "optional"
    assert check.hint is not None


@pytest.mark.parametrize("output_format", ["m4a", "mp3"])
def test_missing_ffmpeg_needs_attention_for_compressed_formats(
    output_format: str, use_ffmpeg: UseFfmpeg, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_ffmpeg(None)
    monkeypatch.setenv("PHEMIUS_FORMAT", output_format)

    check = run_check("ffmpeg")

    assert check.status == "needs_attention"
    assert output_format.upper() in check.detail


def test_hung_check_times_out_without_blocking_the_others(
    hung_model: HungScriptModel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(checks, "CHECK_TIMEOUT_SECONDS", 0.2)

    started = time.perf_counter()
    run = checks.run_checks()
    elapsed = time.perf_counter() - started

    assert elapsed < 1
    statuses = {check.id: check.status for check in run.checks}
    assert statuses.pop("script_model") == "needs_attention"
    assert set(statuses.values()) <= {"ok", "optional"}
    script_check = next(check for check in run.checks if check.id == "script_model")
    assert "did not answer within 0.2 s" in script_check.detail


def test_failing_check_needs_attention_instead_of_failing_the_run(
    use_script_model: UseScriptModel,
) -> None:
    use_script_model(BrokenScriptModel())

    check = run_check("script_model")

    assert check.status == "needs_attention"
    assert "RuntimeError" in check.detail


def test_last_run_is_empty_before_the_first_run() -> None:
    assert checks.last_run() is None


def test_last_run_keeps_the_latest_result_and_summary(
    use_ffmpeg: UseFfmpeg, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_ffmpeg(None)
    monkeypatch.setenv("PHEMIUS_FORMAT", "mp3")

    run = checks.run_checks()

    assert checks.last_run() == run
    assert run.summary.model_dump() == {"ok": 3, "optional": 2, "needs_attention": 1}

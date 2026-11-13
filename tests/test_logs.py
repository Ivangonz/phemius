import json
import logging
from collections.abc import Callable, Iterator

import httpx2
import pytest
import structlog
from openai import DefaultHttpxClient
from openai._utils._logs import setup_logging as openai_setup_logging

from phemius.logs import QUIET_LOGGERS, REDACTED_LOGGERS, configure_logging
from phemius.models.openai_compatible import OpenAICompatibleModel

DOCUMENT_TEXT = "The quarterly migration plan moves billing to the new ledger."
SCRIPT_TEXT = "Here is what changes when billing moves to the new ledger."
API_KEY = "sk-test-secret-key"


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    levels = {name: logging.getLogger(name).level for name in QUIET_LOGGERS}
    root_level = root.level
    yield
    root.setLevel(root_level)
    for name, level in levels.items():
        logging.getLogger(name).setLevel(level)
    structlog.reset_defaults()


def _completion_body(content: str) -> bytes:
    return json.dumps(
        {
            "id": "gen-1",
            "object": "chat.completion",
            "created": 0,
            "model": "local/model",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
        }
    ).encode()


def _write_script() -> None:
    transport = httpx2.MockTransport(
        lambda request: httpx2.Response(200, content=_completion_body(SCRIPT_TEXT))
    )
    model = OpenAICompatibleModel(
        "http://localhost:1234/v1",
        API_KEY,
        "local/model",
        script_max_tokens=100,
        http_client=DefaultHttpxClient(transport=transport),
        max_retries=0,
    )
    model.write_script("Billing migration", DOCUMENT_TEXT, "neutral")


def _written_output(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> str:
    """Everything structlog printed plus every stdlib record a handler emitted."""
    captured = capsys.readouterr()
    return captured.out + captured.err + caplog.text


def _assert_no_private_text(output: str) -> None:
    assert DOCUMENT_TEXT not in output
    assert SCRIPT_TEXT not in output
    assert API_KEY not in output


def test_script_request_at_debug_logs_ids_but_no_private_text(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    configure_logging("DEBUG")

    _write_script()

    output = _written_output(capsys, caplog)
    assert "model_request" in output
    assert "local/model" in output
    _assert_no_private_text(output)


@pytest.mark.parametrize("is_sdk_imported_first", [True, False])
def test_openai_log_debug_does_not_turn_sdk_logging_back_on(
    is_sdk_imported_first: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    # The SDK reads OPENAI_LOG once, on import; calling its setup directly
    # replays that import before or after our own configuration.
    monkeypatch.setenv("OPENAI_LOG", "debug")
    if is_sdk_imported_first:
        openai_setup_logging()
    configure_logging("DEBUG")
    if not is_sdk_imported_first:
        openai_setup_logging()

    _write_script()

    output = _written_output(capsys, caplog)
    assert "model_request" in output
    assert "HTTP Request" not in output
    _assert_no_private_text(output)


@pytest.mark.parametrize(
    "name", [name for name in QUIET_LOGGERS if name not in REDACTED_LOGGERS]
)
def test_third_party_debug_and_info_records_are_dropped(
    name: str,
    request: pytest.FixtureRequest,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_logging("DEBUG")
    third_party = logging.getLogger(f"{name}.client")
    # Simulates an SDK version that logs request options, as older openai did.
    third_party.setLevel(logging.DEBUG)
    request.addfinalizer(lambda: third_party.setLevel(logging.NOTSET))

    third_party.debug("Request options: %s", {"content": DOCUMENT_TEXT})
    third_party.info("HTTP Response: %s", SCRIPT_TEXT)
    third_party.warning("provider_unreachable")

    output = _written_output(capsys, caplog)
    assert "provider_unreachable" in output
    _assert_no_private_text(output)


def _log_phonemizer_failure(logger: logging.Logger) -> None:
    try:
        raise RuntimeError(f"cannot parse {SCRIPT_TEXT}")
    except RuntimeError:
        logger.exception("Failed to phonemize sentence: %s", SCRIPT_TEXT)


# Logger names and calls as in piper-tts 1.8.0; each can carry script text.
@pytest.mark.parametrize(
    ("name", "emit"),
    [
        (
            "piper.voice",
            lambda logger: logger.debug("text=%s, phonemes=%s", SCRIPT_TEXT, []),
        ),
        (
            "piper.phonemize_thai",
            lambda logger: logger.warning("No phonemes for Thai run: %s", SCRIPT_TEXT),
        ),
        ("piper.phonemize_japanese", _log_phonemizer_failure),
    ],
)
def test_piper_records_carry_no_script_text(
    name: str,
    emit: Callable[[logging.Logger], None],
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    configure_logging("DEBUG")

    emit(logging.getLogger(name))

    output = _written_output(capsys, caplog)
    assert SCRIPT_TEXT not in output
    assert "Failed to phonemize" not in output


def test_piper_warnings_still_show_level_and_logger_name(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
) -> None:
    configure_logging("DEBUG")

    _log_phonemizer_failure(logging.getLogger("piper.phonemize_japanese"))

    output = _written_output(capsys, caplog)
    assert "ERROR" in output
    assert "piper.phonemize_japanese" in output
    assert "RuntimeError" in output

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from phemius.voices import ENGINES, Voice, VoiceCheck
from phemius.voices import piper as piper_voices
from tests.voices.fakes import VOICE, UsePiper, fake_fetch

JOE = "piper:en_US-joe-medium"
LESSAC = "piper:en_US-lessac-medium"


class CountingEngine:
    """A hosted-style engine that records each provider call it would send."""

    extension = "wav"

    def __init__(self) -> None:
        self.check_calls = 0

    def voices(self) -> list[Voice]:
        return [Voice(id="hosted:one", label="One", accent=None)]

    def check(self) -> VoiceCheck:
        self.check_calls += 1
        return VoiceCheck(False, "Provider returned 401.", "Check the API key.")

    def synthesize(self, script: str, out_path: Path, voice: str) -> None:
        raise AssertionError("not used")


@pytest.fixture
def piper_engine(isolated_env: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Piper with only Joe downloaded; the catalogue is local, nothing downloads."""
    monkeypatch.setenv("PHEMIUS_TTS", "piper")
    voices_dir = isolated_env / "voices" / "piper"
    voices_dir.mkdir(parents=True)
    for suffix in (piper_voices.MODEL_SUFFIX, piper_voices.CONFIG_SUFFIX):
        (voices_dir / f"en_US-joe-medium{suffix}").write_bytes(b"voice")
    return voices_dir


@pytest.fixture
def counting_engine(monkeypatch: pytest.MonkeyPatch) -> CountingEngine:
    engine = CountingEngine()
    monkeypatch.setitem(ENGINES, "hosted", lambda config: engine)
    monkeypatch.setenv("PHEMIUS_TTS", "hosted")
    return engine


@pytest.mark.usefixtures("piper_engine")
def test_lists_piper_voices_with_install_state_and_licence(
    client: TestClient,
) -> None:
    body = client.get("/api/voices").json()

    voices = {voice["id"]: voice for voice in body["items"]}
    assert body["total"] == len(piper_voices.CATALOGUE)
    assert body["items"][0]["id"] == JOE
    assert voices[JOE]["is_installed"] is True
    assert voices[JOE]["is_default"] is True
    assert voices[JOE]["license"] == "CC0"
    assert voices[LESSAC]["is_installed"] is False
    assert voices[LESSAC]["is_default"] is False
    assert "non-commercial" in voices[LESSAC]["license"]
    assert voices[LESSAC]["size_bytes"] > 0


@pytest.mark.usefixtures("piper_engine")
def test_saved_default_voice_is_listed_first(client: TestClient) -> None:
    client.patch("/api/settings", json={"default_voice": LESSAC})

    items = client.get("/api/voices").json()["items"]

    assert [item["id"] for item in items[:2]] == [LESSAC, JOE]
    assert items[0]["is_default"] is True


@pytest.mark.usefixtures("piper_engine")
def test_voices_order_by_label_and_page(client: TestClient) -> None:
    body = client.get(
        "/api/voices", params={"order_by": "label", "limit": 2, "offset": 1}
    ).json()

    labels = sorted(entry.label for entry in piper_voices.CATALOGUE)
    assert [item["label"] for item in body["items"]] == labels[1:3]
    assert (body["total"], body["limit"], body["offset"]) == (4, 2, 1)


@pytest.mark.parametrize(
    "params",
    [{"order_by": "size; DROP TABLE"}, {"limit": 101}, {"offset": -1}],
)
def test_bad_list_parameters_are_a_422(
    client: TestClient, params: dict[str, str | int]
) -> None:
    response = client.get("/api/voices", params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_listing_voices_sends_no_provider_request(
    client: TestClient, counting_engine: CountingEngine
) -> None:
    client.get("/api/voices")

    assert counting_engine.check_calls == 0


def test_check_returns_the_engine_message_and_hint(
    client: TestClient, counting_engine: CountingEngine
) -> None:
    response = client.post("/api/voices/check")

    assert response.json() == {
        "is_ready": False,
        "message": "Provider returned 401.",
        "hint": "Check the API key.",
    }
    assert counting_engine.check_calls == 1


def test_check_is_not_reachable_with_get(
    client: TestClient, counting_engine: CountingEngine
) -> None:
    response = client.get("/api/voices/check")

    assert response.status_code == 405
    assert counting_engine.check_calls == 0


def test_unknown_engine_lists_no_voices_and_checks_not_ready(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PHEMIUS_TTS", "espeak")

    assert client.get("/api/voices").json()["items"] == []
    assert client.post("/api/voices/check").json()["is_ready"] is False


def _wait_for_installed(client: TestClient, voice_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        items: list[dict[str, Any]] = client.get("/api/voices").json()["items"]
        voice = next(item for item in items if item["id"] == voice_id)
        if voice["download"]["state"] != "downloading":
            return voice
        time.sleep(0.05)
    raise AssertionError("the download did not finish")


def test_download_returns_202_and_progress_shows_on_the_voice(
    client: TestClient, use_piper: UsePiper
) -> None:
    use_piper(fake_fetch)

    response = client.post(f"/api/voices/{VOICE}/download")

    assert response.status_code == 202
    assert response.json()["state"] == "downloading"
    voice = _wait_for_installed(client, VOICE)
    assert voice["is_installed"] is True
    assert voice["download"]["done"] == voice["download"]["total"]


def test_download_for_an_engine_without_downloads_is_a_409(client: TestClient) -> None:
    response = client.post("/api/voices/stub:silent/download")

    assert response.status_code == 409
    assert response.json()["code"] == "voice_download_conflict"
    assert response.json()["hint"]


@pytest.mark.parametrize(
    ("voice_id", "status"),
    [
        ("piper:missing", 404),
        ("kokoro:af_heart", 404),
        ("piper:..", 404),
        ("..%2F..%2Fetc%2Fpasswd", 404),
        ("piper%3A..%5Cwindows", 422),
        ("piper:" + "a" * 200, 422),
    ],
)
def test_hostile_voice_ids_are_a_4xx_in_the_error_shape(
    client: TestClient, use_piper: UsePiper, voice_id: str, status: int
) -> None:
    use_piper(fake_fetch)

    response = client.post(f"/api/voices/{voice_id}/download")

    assert response.status_code == status
    assert {"detail", "code"} <= response.json().keys()

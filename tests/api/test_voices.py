import time
from pathlib import Path
from typing import Any

import httpx2
import pytest
from fastapi.testclient import TestClient

from phemius.errors import VoiceError
from phemius.services import access
from phemius.voices import ENGINES, Voice, VoiceCheck
from phemius.voices import piper as piper_voices
from phemius.voices.base import SAMPLE_TEXT
from tests.voices.fakes import VOICE, UseCounter, UsePiper, fake_fetch

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


def _preview(client: TestClient, voice_id: str = "one") -> httpx2.Response:
    return client.post(f"/api/voices/{voice_id}/preview")


def test_preview_synthesizes_the_sample_once_and_then_serves_the_cache(
    client: TestClient, use_counter: UseCounter
) -> None:
    engine = use_counter("hosted")

    first = _preview(client)
    second = _preview(client, "hosted:one")

    assert first.status_code == second.status_code == 200
    assert engine.calls == [SAMPLE_TEXT]
    played = client.get(first.json()["url"])
    assert played.status_code == 200
    assert played.headers["content-type"] == "audio/wav"


def test_another_engine_with_the_same_voice_name_gets_its_own_sample(
    client: TestClient, use_counter: UseCounter
) -> None:
    first = use_counter("hosted")
    _preview(client)
    second = use_counter("other")

    response = _preview(client)

    assert response.status_code == 200
    assert (len(first.calls), len(second.calls)) == (1, 1)


def test_a_new_base_url_for_the_engine_makes_a_new_sample(
    client: TestClient, use_counter: UseCounter, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = use_counter("openai_speech")
    _preview(client)
    monkeypatch.setenv("PHEMIUS_OPENAI_SPEECH_BASE_URL", "http://127.0.0.1:9999/v1")

    _preview(client)

    assert len(engine.calls) == 2


def test_adding_a_voice_to_the_engine_list_keeps_existing_samples(
    client: TestClient, use_counter: UseCounter, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = use_counter("openai_speech")
    _preview(client)
    monkeypatch.setenv("PHEMIUS_OPENAI_SPEECH_VOICES", "alloy,nova,shimmer")

    _preview(client)

    assert len(engine.calls) == 1


def test_engine_error_is_a_voice_error_and_leaves_no_cached_sample(
    client: TestClient, use_counter: UseCounter, isolated_env: Path
) -> None:
    engine = use_counter("hosted", VoiceError("Provider returned 401.", "Check key."))

    response = _preview(client)
    _preview(client)

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Provider returned 401.",
        "code": "voice_error",
        "hint": "Check key.",
    }
    assert len(engine.calls) == 2
    assert [
        path for path in (isolated_env / "previews").rglob("*") if path.is_file()
    ] == []


def test_preview_file_is_never_generated_by_a_get(
    client: TestClient, use_counter: UseCounter
) -> None:
    engine = use_counter("hosted")

    response = client.get("/api/voices/hosted:one/preview/file")

    assert response.status_code == 404
    assert client.get("/api/voices/one/preview").status_code == 405
    assert engine.calls == []


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


@pytest.mark.parametrize(
    ("voice_id", "status"),
    [
        ("missing", 404),
        ("..", 404),
        # %2F decodes to "/", so no route matches.
        ("..%2F..%2Flibrary.db", 404),
        ("kokoro:af_heart", 404),
        ("hosted%3A..%5Clibrary.db", 422),
        ("a" * 500, 422),
    ],
)
def test_hostile_preview_ids_are_rejected_in_the_error_shape(
    client: TestClient, use_counter: UseCounter, voice_id: str, status: int
) -> None:
    engine = use_counter("hosted")

    response = _preview(client, voice_id)
    file_response = client.get(f"/api/voices/{voice_id}/preview/file")

    assert (response.status_code, file_response.status_code) == (status, status)
    assert {"detail", "code"} <= response.json().keys()
    assert engine.calls == []


@pytest.fixture
def signed_preview_url(network_client: TestClient, use_counter: UseCounter) -> str:
    use_counter("hosted")
    headers = {"Authorization": f"Bearer {access.regenerate_token()}"}
    response = network_client.post("/api/voices/one/preview", headers=headers)
    assert response.status_code == 200
    return str(response.json()["url"])


def test_signed_preview_url_plays_without_the_token(
    network_client: TestClient, signed_preview_url: str
) -> None:
    unsigned = signed_preview_url.partition("?")[0]

    assert "?expires=" in signed_preview_url
    assert network_client.get(signed_preview_url).status_code == 200
    assert network_client.get(unsigned).status_code == 401


def test_tampered_preview_signature_is_rejected(
    network_client: TestClient, signed_preview_url: str
) -> None:
    path, _, query = signed_preview_url.partition("?")
    params = dict(part.split("=") for part in query.split("&"))
    tampered = f"{path}?expires={params['expires']}&sig={'0' * 64}"
    other_voice = signed_preview_url.replace("hosted:one", "hosted:two")

    response = network_client.get(tampered)

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"
    assert network_client.get(other_voice).status_code == 401
    assert network_client.get(f"/api/audio/1/file?{query}").status_code == 401


def test_expired_preview_signature_is_rejected(
    network_client: TestClient,
    use_counter: UseCounter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(access, "AUDIO_URL_LIFETIME_SECONDS", -1)
    use_counter("hosted")
    headers = {"Authorization": f"Bearer {access.regenerate_token()}"}
    url = network_client.post("/api/voices/one/preview", headers=headers).json()["url"]

    response = network_client.get(url)

    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"

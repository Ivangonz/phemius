from pathlib import Path

import pytest
from freezegun import freeze_time

from phemius.config import AccessMode
from phemius.errors import PhemiusError
from phemius.services import access
from phemius.services.access import BindOptions
from phemius.store import access as access_store
from phemius.store import database


@pytest.fixture(autouse=True)
def library(isolated_env: Path) -> None:
    database.init_database(isolated_env / "library.db")


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("local", BindOptions(host="127.0.0.1", is_proxy_trusted=False)),
        ("network", BindOptions(host="0.0.0.0", is_proxy_trusted=False)),
        ("proxy", BindOptions(host="127.0.0.1", is_proxy_trusted=True)),
    ],
)
def test_bind_options_follow_the_access_mode(
    mode: AccessMode, expected: BindOptions
) -> None:
    assert access.bind_options(mode) == expected


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "localhost", "::1"])
def test_local_mode_accepts_a_loopback_host(host: str) -> None:
    assert access.bind_options("local", host).host == host


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.20", "phemius.lan"])
def test_local_mode_refuses_a_host_beyond_this_computer(host: str) -> None:
    with pytest.raises(PhemiusError) as raised:
        access.bind_options("local", host)

    assert host in raised.value.message
    assert raised.value.hint is not None
    assert "PHEMIUS_ACCESS_MODE=network" in raised.value.hint


def test_local_mode_refuses_a_public_host_even_with_an_env_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Local mode never checks the token, so setting one would not protect it.
    monkeypatch.setenv("PHEMIUS_ACCESS_TOKEN", "a" * 32)

    with pytest.raises(PhemiusError):
        access.bind_options("local", "0.0.0.0")


@pytest.mark.parametrize("mode", ["network", "proxy"])
def test_modes_that_require_a_token_accept_any_host(mode: AccessMode) -> None:
    bind = access.bind_options(mode, "0.0.0.0")

    assert bind.host == "0.0.0.0"
    assert bind.is_proxy_trusted is (mode == "proxy")


@pytest.mark.parametrize(
    ("mode", "is_required"), [("local", False), ("network", True), ("proxy", True)]
)
def test_token_is_required_beyond_local_mode(
    mode: AccessMode, is_required: bool
) -> None:
    assert access.is_token_required(mode) is is_required


def test_ensure_creates_a_token_only_once() -> None:
    created = access.ensure_access_token()

    assert created is not None
    assert created.startswith("phm_")
    assert access.ensure_access_token() is None
    assert access.is_valid_token(created)


def test_local_mode_creates_no_token_without_the_env_variable() -> None:
    assert access.prepare_access_token("local") is None
    assert access_store.read_token_hash() is None


def test_env_token_applies_in_any_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_ACCESS_TOKEN", "0123456789abcdef")

    assert access.prepare_access_token("local") is None
    assert access.is_valid_token("0123456789abcdef")


def test_only_a_hash_of_the_token_is_stored() -> None:
    token = access.regenerate_token()

    stored = access_store.read_token_hash()

    assert stored is not None
    assert token not in stored


def test_regenerating_invalidates_the_old_token() -> None:
    old_token = access.regenerate_token()

    new_token = access.regenerate_token()

    assert new_token != old_token
    assert not access.is_valid_token(old_token)
    assert access.is_valid_token(new_token)


@pytest.mark.parametrize("candidate", ["", "phm_wrong", None])
def test_invalid_tokens_are_rejected(candidate: str | None) -> None:
    access.regenerate_token()

    assert not access.is_valid_token(candidate)


def test_no_token_is_valid_before_one_exists() -> None:
    assert not access.is_valid_token("phm_anything")


def test_signed_audio_url_is_valid_until_it_expires() -> None:
    access.regenerate_token()
    with freeze_time() as frozen:
        signed = access.sign_audio_url(3)
        expires = str(signed.expires)
        is_valid_now = access.is_valid_audio_signature(3, expires, signed.signature)
        frozen.tick(access.AUDIO_URL_LIFETIME_SECONDS + 1)
        is_valid_later = access.is_valid_audio_signature(3, expires, signed.signature)

    assert is_valid_now
    assert not is_valid_later


@pytest.mark.parametrize("expires", [None, "", "soon", "-1", "²", "9" * 5000])
def test_audio_signature_with_a_malformed_expiry_is_rejected(
    expires: str | None,
) -> None:
    access.regenerate_token()
    signed = access.sign_audio_url(3)

    assert not access.is_valid_audio_signature(3, expires, signed.signature)


@pytest.mark.parametrize("signature", ["", "é", "0" * 64])
def test_audio_signature_that_does_not_match_is_rejected(signature: str) -> None:
    access.regenerate_token()
    signed = access.sign_audio_url(3)

    assert not access.is_valid_audio_signature(3, str(signed.expires), signature)


def test_audio_url_is_unsigned_without_a_token() -> None:
    signed = access.sign_audio_url(3)

    assert signed.signature is None
    assert not access.is_valid_audio_signature(3, str(signed.expires), "")

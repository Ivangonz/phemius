import pytest

from phemius.config import load_config
from phemius.models.base import TokenUsage
from phemius.services.usage import TokenPrices, configured_prices, script_cost

PRICES = TokenPrices(input_per_million=3.0, output_per_million=15.0)
COUNTED = TokenUsage(input_tokens=1200, output_tokens=300)


def test_cost_is_estimated_from_configured_prices() -> None:
    assert script_cost(COUNTED, PRICES) == pytest.approx(0.0081)


def test_cost_the_provider_reports_wins_over_configured_prices() -> None:
    usage = TokenUsage(input_tokens=1200, output_tokens=300, provider_cost_usd=0.002)

    assert script_cost(usage, PRICES) == 0.002


def test_local_model_costs_nothing_even_with_prices_set() -> None:
    usage = TokenUsage(input_tokens=1200, output_tokens=300, is_local=True)

    assert script_cost(usage, PRICES) == 0.0


def test_cost_is_unknown_without_prices() -> None:
    assert script_cost(COUNTED, None) is None


def test_cost_is_unknown_when_the_provider_reported_no_tokens() -> None:
    assert script_cost(TokenUsage(), PRICES) is None


def test_prices_come_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_INPUT_PRICE", "3")
    monkeypatch.setenv("PHEMIUS_SCRIPT_OUTPUT_PRICE", "15.5")

    assert configured_prices(load_config()) == TokenPrices(3.0, 15.5)


def test_one_price_alone_is_not_enough_to_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PHEMIUS_SCRIPT_INPUT_PRICE", "3")

    assert configured_prices(load_config()) is None

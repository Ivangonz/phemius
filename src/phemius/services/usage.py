"""The cost of a script: what the provider charged, or an estimate from prices.

A cost that cannot be known stays None; it is never guessed.
"""

from dataclasses import dataclass

from phemius.config import Config
from phemius.models.base import TokenUsage
from phemius.store.jobs import JobUsage

TOKENS_PER_PRICE_UNIT = 1_000_000


@dataclass(frozen=True)
class TokenPrices:
    """US dollars per million tokens, as the user configured them."""

    input_per_million: float
    output_per_million: float


def configured_prices(config: Config) -> TokenPrices | None:
    if config.script_input_price is None or config.script_output_price is None:
        return None
    return TokenPrices(config.script_input_price, config.script_output_price)


def script_cost(usage: TokenUsage, prices: TokenPrices | None) -> float | None:
    """US dollars spent, preferring the provider's own figure over an estimate."""
    if usage.is_local:
        return 0.0
    if usage.provider_cost_usd is not None:
        return usage.provider_cost_usd
    if prices is None or usage.input_tokens is None or usage.output_tokens is None:
        return None
    spent = (
        usage.input_tokens * prices.input_per_million
        + usage.output_tokens * prices.output_per_million
    )
    return spent / TOKENS_PER_PRICE_UNIT


def job_usage(usage: TokenUsage, config: Config) -> JobUsage:
    return JobUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=script_cost(usage, configured_prices(config)),
    )

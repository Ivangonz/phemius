"""The cost of a script: what the provider charged, or an estimate from prices.

A cost that cannot be known stays None; it is never guessed.
"""

from collections.abc import Sequence
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


def total_usage(usages: Sequence[TokenUsage]) -> TokenUsage:
    """The usage of several requests. A figure any of them left out stays None."""
    return TokenUsage(
        input_tokens=_total([usage.input_tokens for usage in usages]),
        output_tokens=_total([usage.output_tokens for usage in usages]),
        provider_cost_usd=_total([usage.provider_cost_usd for usage in usages]),
        is_local=all(usage.is_local for usage in usages),
    )


def _total[Number: (int, float)](values: list[Number | None]) -> Number | None:
    known = [value for value in values if value is not None]
    if not known or len(known) < len(values):
        return None
    return sum(known[1:], start=known[0])


def job_usage(usage: TokenUsage, config: Config) -> JobUsage:
    return JobUsage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_usd=script_cost(usage, configured_prices(config)),
    )

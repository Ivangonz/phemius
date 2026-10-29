"""Base for adapters that talk to a chat completion API.

Subclasses implement only `_chat` (the transport and its error mapping); prompts,
analysis parsing and the cut-off check live here so every provider behaves the same.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from phemius.errors import ModelError
from phemius.models import prompts
from phemius.models.base import Analysis, Script, ScriptModelCheck, TokenUsage

CHECK_MAX_TOKENS = 16


@dataclass(frozen=True)
class ChatReply:
    content: str
    is_truncated: bool
    usage: TokenUsage = field(default_factory=TokenUsage)


class ChatScriptModel(ABC):
    length_hint = "Raise PHEMIUS_SCRIPT_MAX_TOKENS or use a shorter document."

    def __init__(self, model: str, script_max_tokens: int) -> None:
        self.model = model
        self.script_max_tokens = script_max_tokens

    @abstractmethod
    def _chat(self, system: str, user: str, max_tokens: int) -> ChatReply:
        """Send one chat request. Raises `ModelError` with a status-only message."""

    def analyze(self, title: str, text: str) -> Analysis:
        reply = self._complete(
            prompts.ANALYSIS_SYSTEM,
            prompts.analysis_prompt(title, text),
            prompts.ANALYSIS_MAX_TOKENS,
        )
        return prompts.parse_analysis(reply.content, text)

    def write_script(self, title: str, text: str, tone: str) -> Script:
        reply = self._complete(
            prompts.script_system(tone),
            prompts.script_prompt(title, text),
            self.script_max_tokens,
        )
        return Script(reply.content.strip(), reply.usage)

    def check(self) -> ScriptModelCheck:
        started = time.perf_counter()
        try:
            # A cut-off reply still proves the model answered, so it is accepted.
            self._chat("Reply with the word OK.", "OK?", CHECK_MAX_TOKENS)
        except ModelError as error:
            return ScriptModelCheck(
                is_reachable=False,
                model=self.model,
                error=error.message,
                hint=error.hint,
            )
        latency_ms = (time.perf_counter() - started) * 1000
        return ScriptModelCheck(
            is_reachable=True, model=self.model, latency_ms=latency_ms
        )

    def _complete(self, system: str, user: str, max_tokens: int) -> ChatReply:
        reply = self._chat(system, user, max_tokens)
        if reply.is_truncated:
            # Never silently ship a script that was cut off mid-document.
            raise ModelError(
                f"Model output hit the {max_tokens}-token limit.",
                hint=self.length_hint,
            )
        return reply

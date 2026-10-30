import threading

from phemius.services import previews, synthesis
from phemius.voices.base import SAMPLE_TEXT
from tests.voices.fakes import UseCounter


def test_preview_waits_for_a_narration_holding_the_synthesis_lock(
    use_counter: UseCounter,
) -> None:
    engine = use_counter("hosted")
    worker = threading.Thread(target=previews.create_preview, args=("one",))

    with synthesis.lock:
        worker.start()
        worker.join(0.2)
        is_waiting = worker.is_alive()
        calls_while_locked = list(engine.calls)
    worker.join(5)

    assert is_waiting
    assert calls_while_locked == []
    assert engine.calls == [SAMPLE_TEXT]

from phemius.voices.text import pack_chunks


def _words(text: str) -> list[str]:
    return text.split()


def test_pack_chunks_keeps_every_chunk_under_the_limit_without_losing_words() -> None:
    script = "\n\n".join(
        " ".join(f"Sentence {para}-{index} is short." for index in range(12))
        for para in range(10)
    )

    chunks = pack_chunks(script, limit=300)

    assert len(chunks) > 1
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert _words(" ".join(chunks)) == _words(script)


def test_pack_chunks_packs_short_paragraphs_into_one_request() -> None:
    script = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."

    assert pack_chunks(script, limit=1000) == [
        "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    ]


def test_pack_chunks_splits_a_sentence_longer_than_the_limit_at_words() -> None:
    sentence = " ".join(["word"] * 100) + "."

    chunks = pack_chunks(sentence, limit=50)

    assert all(len(chunk) <= 50 for chunk in chunks)
    assert _words(" ".join(chunks)) == _words(sentence)


def test_pack_chunks_of_blank_script_is_empty() -> None:
    assert pack_chunks("  \n\n ", limit=100) == []

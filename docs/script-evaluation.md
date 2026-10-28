# Evaluating spoken scripts

Phemius narrates what the script model writes, so a stray asterisk or a URL ends
up read aloud. This page explains how scripts are prepared and how to check
their quality with the evaluation set.

## How a document is prepared

Before any model sees a document, `models/spoken_text.py` rewrites it the same
way for every provider:

- Fenced and indented code blocks become a `[Code example ...]` line, the code,
  and `[End of code example.]`. The prompt tells the model to describe the code
  in words and never read it. The offline rules replace the whole block with a
  short mention.
- Markdown tables become a list of columns followed by one `label: value` line
  per row.
- Links keep their text and lose the URL; bare URLs, autolinks, reference
  definitions and images are removed.

The prompt in `models/prompts.py` also asks the model to expand an acronym on
first use, say file names naturally and never output markdown symbols or URLs.
The 40,000-character limit applies to the prepared text, and a longer document
still fails with a hint rather than being cut.

## The evaluation set

Five small documents live in `tests/fixtures/script_eval/`:

| Document | What it exercises |
| --- | --- |
| `code_blocks.md` | Fenced code with and without a language, a URL inside code, an indented command |
| `tables.md` | Two tables with alignment markers and multi-word cells |
| `links.md` | Inline links with titles, reference links, an image, bare URLs and autolinks |
| `acronyms.md` | Acronyms (API, TLS, OIDC) and file names (`gateway.yaml`, `README.md`) |
| `narrative.md` | Plain prose that should pass through almost unchanged |

Each case in `tests/services/test_script_eval.py` checks these properties:

- **No markdown symbols.** The script contains no backticks, asterisks, pipes,
  brackets, heading or quote markers, or bullet markers at the start of a line.
- **No raw URLs.** Nothing starting with `http://`, `https://` or `www.`.
- **Length ratio.** Script length divided by source length stays within the
  case's band (0.3 to 2.5 by default). Too low means the model dropped content;
  too high means it padded or invented.
- **Kept phrases.** The text sent to the model still holds the link text, table
  values and code that the listener should hear about.

## Running it

In CI, `uv run pytest` runs the set twice without a network: once with a fake
model that records the prepared text (checking the input), and once with the
offline rules (checking a full script).

To try a real model, configure it as you would for Phemius and opt in:

```bash
export PHEMIUS_SCRIPT_PROVIDER=ollama PHEMIUS_OLLAMA_MODEL=llama3.1
PHEMIUS_EVAL_LIVE=1 uv run pytest -m live_model -s tests/services/test_script_eval.py
```

The live tests are marked `live_model` and skipped unless `PHEMIUS_EVAL_LIVE=1`.
They use your `PHEMIUS_*` variables and API keys from the environment (saved
settings in your library are not read), print each script so you can listen
for tone and flow, and fail on the same properties as above. Run them after
changing the prompt or the preparation rules, and note the model you used in
the pull request.

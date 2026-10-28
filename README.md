# Phemius

Hear your docs.

Phemius turns documentation into narrated audio. You add a document, Phemius
categorizes it and suggests a tone, rewrites it as a script meant to be listened
to, and reads it aloud with a text-to-speech voice. The audio stays in a local
library that you play in the browser.

Phemius is open source (Apache-2.0) and self-hosted. It runs on your machine,
keeps its library in one folder, and works fully offline.

## What it does today

- **Add documents** by dragging them onto the web page, by uploading through the
  API, or by dropping them into a watched folder. Supported types: `.md`,
  `.markdown`, `.txt`, `.rst`, `.html`, `.htm`, `.docx` and `.pdf`.
- **Categorize and suggest a tone.** Each document gets a category (for example
  "how-to / tutorial" or "meeting notes / status"), a one-sentence summary and a
  suggested tone: `neutral`, `conversational`, `podcast`, `teacher` or `executive`.
- **Write a spoken script.** With an [OpenRouter](https://openrouter.ai) API key, a
  hosted model writes the script. Without a key, offline rules strip the markdown
  and make lists and code speakable.
- **Narrate locally** with [Kokoro](https://github.com/hexgrad/kokoro) and one of
  11 American and British English voices.
- **Play from the library.** Generate more versions of a document with another
  tone or voice, and read the script behind each one.

Not available yet: Docker and `uv tool install` installs, other model providers
(OpenAI-compatible servers, Ollama), other voice engines, GitHub and Confluence
sources, and an access token. Until the access token exists, keep Phemius bound
to `127.0.0.1`, as `make run` does.

## Contents

- [Quick start with Docker](#quick-start-with-docker)
- [Quick start with uv tool install](#quick-start-with-uv-tool-install)
- [Run from source](#run-from-source)
- [First run](#first-run)
- [Script model](#script-model)
- [Watched folder](#watched-folder)
- [Configuration](#configuration)
- [API](#api)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Quick start with Docker

Coming soon.

## Quick start with uv tool install

Coming soon.

## Run from source

### Prerequisites

- macOS or Linux with `git` and `make`.
- [uv](https://docs.astral.sh/uv/getting-started/installation/). You do not need
  to install Python yourself: uv downloads Python 3.12 for the project if it is
  missing. Phemius needs exactly Python 3.12 because Kokoro supports only 3.10 to
  3.12.
- Optional: [ffmpeg](https://ffmpeg.org) on your `PATH`, only if you want M4A or
  MP3 files instead of WAV (see `PHEMIUS_FORMAT`).

Install uv if you do not have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install and run

```bash
git clone https://github.com/Ivangonz/phemius.git
cd phemius
make install   # uv sync --extra kokoro: dependencies plus the Kokoro voice engine
make run       # dev server with reload on http://127.0.0.1:8000
```

Open <http://127.0.0.1:8000>, drop a document on the page (try
`samples/deploy-guide.md`), and press play when its audio shows up.

To use another port or address:

```bash
make run PORT=8001
```

Stop the server with `Ctrl+C`. Your library stays in `~/.phemius`.

## First run

**The first Kokoro narration downloads the voice model (about 300 MB).** It is
fetched once, on the first audio you generate, so that audio takes noticeably
longer and needs a network connection. Later narrations run offline.

To try the whole flow without the download, use the stub voice engine. It writes
silent WAV files (about one second per sentence group) so you can check uploads,
scripts and the library without Kokoro:

```bash
PHEMIUS_TTS=stub make run
```

The stub works even if you skipped the Kokoro extra and installed with plain
`uv sync`.

Each audio moves through `pending`, `scripting`, `synthesizing` and then `done`
or `error`. The page polls for updates and shows the status in text. A failed
audio shows its error message and a hint on the document card.

## Script model

Phemius writes scripts in one of two ways:

| Setup | Who writes the script | Network |
| --- | --- | --- |
| No `OPENROUTER_API_KEY` | Offline rules: strip markdown, turn headings into "Section: ..." and numbered lists into "Step 1. ...", and replace code blocks with a short spoken note | None |
| `OPENROUTER_API_KEY` set | The model in `PHEMIUS_MODEL` on OpenRouter (default `anthropic/claude-sonnet-4.5`) | Calls `openrouter.ai` |

To use a hosted model:

```bash
export OPENROUTER_API_KEY=sk-or-...
export PHEMIUS_MODEL=anthropic/claude-sonnet-4.5   # optional; any slug from openrouter.ai/models
make run
```

The status line at the top of the page shows which mode is active.

When a model is configured and a call fails:

- **Script writing** fails the audio. Its status becomes `error`, and the card
  shows the reason with a hint, for example `OpenRouter returned 401. Check
  OPENROUTER_API_KEY.` Phemius never falls back silently or keeps a script that
  was cut off: if the model hits `PHEMIUS_SCRIPT_MAX_TOKENS`, the audio fails
  with a hint to raise the limit.
- **Categorizing** falls back to the offline rules so the document is still
  added. The page shows the error at the top: "LLM call failed, used offline
  fallback: ...".

Limits to know about:

- Only the first 40,000 characters of a document are sent to the model when it
  writes the script, and the first 6,000 when it categorizes.
- Your API key is read from the environment only. It is not stored, logged or
  returned by the API.

## Watched folder

Set `PHEMIUS_WATCH_DIR` to have Phemius import documents from a folder:

```bash
PHEMIUS_WATCH_DIR=~/Documents/listen make run
```

- The folder is created if it does not exist, and subfolders are included.
- On startup, every supported file already in the folder is imported.
- While the server runs, new and changed files are imported about a second after
  they are written, and their audio is generated automatically.
- Hidden files (names starting with `.`) and unsupported types are skipped.
- Documents are deduplicated by content: a file whose text is already in the
  library is not imported again, and no new audio is generated for it.
- Editing a file imports its new text as a new document. The earlier version
  and its audio stay in the library.

## Configuration

Phemius reads its configuration from environment variables when it needs them.
Restart the server after changing one. An empty value counts as unset.

| Variable | Default | Description |
| --- | --- | --- |
| `PHEMIUS_DATA_DIR` | `~/.phemius` | Library folder. Holds `library.db` (SQLite) and `audio/`. Created on startup. |
| `PHEMIUS_TTS` | `kokoro` | Voice engine: `kokoro` or `stub` (silent audio, no model download). Any other value uses Kokoro. |
| `PHEMIUS_VOICE` | `af_heart` | Default voice for new audio. Use one of the voice ids listed in `GET /api/config`, for example `af_heart`, `am_michael` or `bf_emma`. |
| `PHEMIUS_MODEL` | `anthropic/claude-sonnet-4.5` | OpenRouter model slug. Used only when `OPENROUTER_API_KEY` is set. |
| `PHEMIUS_SCRIPT_MAX_TOKENS` | `8000` | Maximum tokens the model may write for one script. Must be a whole number, or the server does not start. |
| `PHEMIUS_WATCH_DIR` | not set (no folder watched) | Folder to import documents from. See [Watched folder](#watched-folder). |
| `PHEMIUS_FORMAT` | `wav` | Audio file format: `wav`, `m4a`, `mp4` or `mp3`. Formats other than WAV need `ffmpeg` on your `PATH`. Without ffmpeg, or with an unknown value, Phemius keeps the WAV file. |
| `PHEMIUS_LOG_LEVEL` | `info` | Log level: `debug`, `info`, `warning` or `error`. |
| `OPENROUTER_API_KEY` | not set (offline rules) | OpenRouter API key for writing scripts and categorizing documents. See [Script model](#script-model). |

`make run` also accepts `HOST` (default `127.0.0.1`) and `PORT` (default `8000`)
as make variables, for example `make run PORT=8001`.

## API

The web page uses a small JSON API, which you can also call directly. Interactive
docs are at <http://127.0.0.1:8000/docs>.

| Method and path | Description |
| --- | --- |
| `GET /api/health` | `{"status": "ok"}` when the database is readable and the data folder is writable; `503` otherwise |
| `GET /api/config` | Tones, voices, default voice, watched folder, script model and voice engine in use |
| `GET /api/docs` | Library: all documents, newest first, each with its audio |
| `POST /api/docs` | Upload one or more files (multipart field `files`). Generates audio unless `?auto_audio=false` |
| `GET /api/docs/{id}` | One document, including its extracted text |
| `POST /api/docs/{id}/audio` | Generate another audio. Body: `{"tone": "teacher", "voice": "bf_emma"}`; both fields optional |
| `GET /api/audio/{id}` | One audio, including its status, script and error |
| `GET /api/audio/{id}/file` | The audio file, once its status is `done` |

Upload a document from the command line:

```bash
curl -F files=@samples/deploy-guide.md http://127.0.0.1:8000/api/docs
# [{"file":"deploy-guide.md","doc_id":1,"duplicate":false,"error":null}]
```

Errors share one shape:

```json
{
  "detail": "Unknown tone; choose from ['neutral', 'conversational', 'podcast', 'teacher', 'executive']",
  "code": "invalid_input",
  "errors": [{"field": "tone", "message": "Unknown tone; ..."}]
}
```

A `hint` field is added when Phemius knows how to fix the problem.

## Troubleshooting

### Check that the server is healthy

```bash
curl http://127.0.0.1:8000/api/health
# {"status":"ok"}
```

A `503` response names the problem and how to fix it, for example:

```json
{"detail": "The data folder is not writable.", "code": "unavailable", "hint": "Make /path/to/folder writable or set PHEMIUS_DATA_DIR."}
```

### "Kokoro is not installed"

The audio card shows:

```text
Error: Kokoro is not installed. Run `uv sync --extra kokoro`, or set PHEMIUS_TTS=stub to test.
```

The Kokoro extra is missing from the project environment. Install it:

```bash
make install
```

Running plain `uv sync` removes the extra again, because uv syncs the environment
exactly to what you ask for. Use `make install` or `uv sync --extra kokoro`.

### Wrong Python version

Phemius requires Python 3.12 (`>=3.12,<3.13`). Check what the project uses:

```bash
uv run python --version
# Python 3.12.x
```

If it shows another version, or `make install` fails while installing Kokoro:

- Do not install with `pip` into another Python. Use `uv`, which picks 3.12.
- If uv warns that `VIRTUAL_ENV` does not match the project environment, run
  `unset VIRTUAL_ENV` (or `deactivate`) and try again.
- Recreate the environment: `rm -rf .venv && make install`.

### Port already in use

```text
ERROR:    [Errno 48] error while attempting to bind on address ('127.0.0.1', 8000): address already in use
```

Another process (often another Phemius) is using port 8000. Stop it, or run on
another port:

```bash
lsof -i :8000          # find the process
make run PORT=8001     # or use another port
```

On Linux the error number is 98 instead of 48.

### Audio stays WAV when I set `PHEMIUS_FORMAT`

ffmpeg is not on your `PATH`. Install it (for example `brew install ffmpeg` or
`sudo apt install ffmpeg`) and restart the server. Phemius keeps the WAV file
rather than failing.

### The server does not start after setting a variable

`PHEMIUS_SCRIPT_MAX_TOKENS` must be a whole number such as `8000`. Any other
value stops the server during startup with `Application startup failed`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and
[docs/architecture.md](docs/architecture.md) for how Phemius is built and the
decisions behind it.

## License

Apache-2.0. See [LICENSE](LICENSE).

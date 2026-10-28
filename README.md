# Phemius

Hear your docs.

Phemius turns documentation into narrated audio. You add a document, Phemius
categorizes it and suggests a tone, rewrites it as a script meant to be listened
to, and reads it aloud with a text-to-speech voice. The audio stays in a local
library.

Phemius is open source (Apache-2.0) and self-hosted. It runs on your machine,
keeps its library in one folder, and works fully offline.

## What it does today

- **Add documents** through the API or by dropping them into a watched folder.
  Supported types: `.md`, `.markdown`, `.txt`, `.rst`, `.html`, `.htm`, `.docx`
  and `.pdf`.
- **Categorize and suggest a tone.** Each document gets a category (for example
  "how-to / tutorial" or "meeting notes / status"), a one-sentence summary and a
  suggested tone: `neutral`, `conversational`, `podcast`, `teacher` or `executive`.
- **Write a spoken script** with any server that speaks the OpenAI chat API:
  [OpenRouter](https://openrouter.ai), OpenAI, or a local server such as LM
  Studio, vLLM or LiteLLM. Offline rules need no model at all.
- **Narrate locally** with [Kokoro](https://github.com/hexgrad/kokoro) and one of
  11 American and British English voices, with the lighter
  [Piper](https://github.com/OHF-Voice/piper1-gpl) for small machines, or with
  hosted voices from OpenAI, a self-hosted OpenAI-compatible speech server, or
  ElevenLabs.
- **Keep a library** of documents and their audio, with more versions per
  document in another tone or voice.
- **Save settings** through `PATCH /api/settings`, with environment variables
  taking precedence.

The web UI is in early development. Its Library, Sources, Queue and Settings
pages are placeholders, so for now you add documents and play audio through the
API (see [Hear your first document](#hear-your-first-document)).

Not available yet: Docker and `uv tool install` installs, GitHub and Confluence
sources.

## Contents

- [Quick start with Docker](#quick-start-with-docker)
- [Quick start with uv tool install](#quick-start-with-uv-tool-install)
- [Run from source](#run-from-source)
- [Hear your first document](#hear-your-first-document)
- [First run](#first-run)
- [Script model](#script-model)
- [API keys](#api-keys)
- [Voices](#voices)
- [Watched folder](#watched-folder)
- [Access from other devices](#access-from-other-devices)
- [Configuration](#configuration)
- [API](#api)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Quick start with Docker

Coming soon. Installed copies will include the built UI, so they will not need
Node.

## Quick start with uv tool install

Coming soon.

## Run from source

### Prerequisites

- macOS or Linux with `git` and `make`.
- [uv](https://docs.astral.sh/uv/getting-started/installation/). You do not need
  to install Python yourself: uv downloads Python 3.12 for the project if it is
  missing. Phemius needs exactly Python 3.12 because Kokoro supports only 3.10 to
  3.12.
- [Node.js](https://nodejs.org) 22 with npm, for the web UI (the version is
  pinned in `frontend/.nvmrc`). Node is needed only to develop or build the UI;
  the Phemius server itself never runs on Node.
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
make install   # uv sync --extra kokoro, then npm install in frontend/
make run       # API on 127.0.0.1:8000 (phemius serve) and the UI dev server on port 5173
```

`make run` starts two servers with reload. Stop both with `Ctrl+C`.

| What | URL |
| --- | --- |
| Web UI (Vite dev server; it proxies `/api` to the API) | <http://localhost:5173> |
| API | <http://127.0.0.1:8000/api/health> |
| Interactive API docs | <http://127.0.0.1:8000/docs> |

The built UI is not committed. The API at port 8000 serves a UI only after you
build it; until then, `http://127.0.0.1:8000/` returns `Not Found`. To serve
the UI from the API, as installed copies will:

```bash
make build                 # builds frontend/ into src/phemius/static (git-ignored)
make run backend           # then open http://127.0.0.1:8000
```

Build before starting the server; a server that is already running does not
pick up a new build.

### Run without Node

The API, the pipeline and the interactive API docs work without Node:

```bash
make install backend   # uv sync --extra kokoro only
make run backend       # API only, on http://127.0.0.1:8000
```

Your library stays in `~/.phemius`.

## Hear your first document

With the server running, upload a sample from the repository:

```bash
curl -F files=@samples/deploy-guide.md http://127.0.0.1:8000/api/docs
# [{"file":"deploy-guide.md","doc_id":1,"duplicate":false,"error":null}]
```

Phemius generates its audio in the background. Check its status:

```bash
curl http://127.0.0.1:8000/api/docs
```

The `audio` list of the document moves through `pending`, `scripting`,
`synthesizing` and then `done` or `error`. When it is `done`, open the file in
your browser to play it:

```text
http://127.0.0.1:8000/api/audio/1/file
```

You can also upload from the browser: open <http://127.0.0.1:8000/docs>, expand
`POST /api/docs`, choose "Try it out" and pick a file.

An audio with status `error` has an `error` field with the message and a hint.

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

The stub works even if you installed without the Kokoro extra (plain `uv sync`).

## Script model

`PHEMIUS_SCRIPT_PROVIDER` picks who categorizes documents and writes scripts:

| Provider | What it does | Network |
| --- | --- | --- |
| `offline` | Rules: strip markdown, turn headings into "Section: ..." and numbered lists into "Step 1. ...", and replace code blocks with a short spoken note | None |
| `openrouter` | The model in `PHEMIUS_MODEL` on OpenRouter (default `anthropic/claude-sonnet-4.5`), with `OPENROUTER_API_KEY` | Calls `openrouter.ai` |
| `openai` | The model in `PHEMIUS_MODEL` on OpenAI (set it, for example `gpt-4.1-mini`), with `OPENAI_API_KEY` | Calls `api.openai.com` |
| `openai_compatible` | The model in `PHEMIUS_MODEL` on the server at `PHEMIUS_SCRIPT_BASE_URL`, with the optional `PHEMIUS_SCRIPT_API_KEY` | Calls that server only |
| `ollama` | The model in `PHEMIUS_OLLAMA_MODEL` on a local [Ollama](https://ollama.com) server (default `llama3.2`) | Only your Ollama server |

When `PHEMIUS_SCRIPT_PROVIDER` is not set, Phemius uses `openrouter` if an
OpenRouter API key is configured and `offline` otherwise. So the shortest setup
for a hosted model is:

```bash
export OPENROUTER_API_KEY=sk-or-...
export PHEMIUS_MODEL=anthropic/claude-sonnet-4.5   # optional; any slug from openrouter.ai/models
make run
```

`openai` and `openrouter` are presets of `openai_compatible` that only fill in
the base URL and read their own key. To use LM Studio, vLLM, LiteLLM or any
other server that speaks the OpenAI chat completions API, point Phemius at its
base URL (usually ending in `/v1`):

```bash
export PHEMIUS_SCRIPT_PROVIDER=openai_compatible
export PHEMIUS_SCRIPT_BASE_URL=http://localhost:1234/v1   # LM Studio's default
export PHEMIUS_MODEL=qwen2.5-7b-instruct                  # a model the server lists
export PHEMIUS_SCRIPT_API_KEY=...                         # only if the server needs one
make run
```

Without `PHEMIUS_SCRIPT_API_KEY`, Phemius sends a placeholder key, which local
servers ignore; it never sends your `OPENAI_API_KEY` to another server.

`GET /api/config` reports the provider in use (`script_provider`) and the model.

### Local model with Ollama

Ollama keeps everything on your machine: with Ollama and Kokoro, Phemius needs
no network at all once the models are downloaded.

```bash
ollama pull llama3.2                       # once; any chat model works
export PHEMIUS_SCRIPT_PROVIDER=ollama
export PHEMIUS_OLLAMA_MODEL=llama3.2       # optional; the default
export PHEMIUS_OLLAMA_URL=http://localhost:11434   # optional; the default
make run
```

- Use a name from `ollama list`. A name without a tag means `:latest`.
- Small local models are slow on a CPU, so a request may take up to
  `PHEMIUS_OLLAMA_TIMEOUT` seconds (default 600) before it fails.
- Phemius removes the code fences, markdown and "Here is the script:" lead-ins
  that small models add, so the voice reads only the script.
- Phemius sizes Ollama's context window to fit each document, so a long
  document is never cut off without notice. Larger documents need more memory.
- Ollama failures carry a fix: `Ollama is not running at ...` (start it with
  `ollama serve`), `Ollama model '...' is not pulled.` (run `ollama pull ...`) or
  `Ollama did not answer in time.` (raise `PHEMIUS_OLLAMA_TIMEOUT`).

When a configured model fails:

- **Script writing** fails the audio. Its status becomes `error`, and its
  `error` field holds the reason and a hint, for example `OpenRouter returned
  401. Check OPENROUTER_API_KEY.` A rejected key (401), missing credit (402),
  an unknown model (404), a rate limit (429), a server that refuses the
  connection and a server that does not answer in time each get their own hint;
  errors name a self-hosted server by its host and port, for example `Could not
  reach localhost:1234.` Phemius never falls back to an offline script
  and never keeps a script that was cut off: if the model hits
  `PHEMIUS_SCRIPT_MAX_TOKENS`, the audio fails with a hint to raise the limit.
- **Long documents** fail the same way. With a model provider, one script covers
  up to 40,000 characters of text; a longer document fails with an error that
  states its length and suggests splitting it. The offline rules have no limit.
- **Categorizing** falls back to the offline rules so the document is still
  added. `GET /api/config` shows the error in `llm_error`. Categorizing reads
  only the first 6,000 characters of a document.

## API keys

For a deployment, pass API keys as environment variables, or keep them in a
`.env` file that you pass to Docker (`docker run --env-file .env ...`) and do not
commit. An environment variable always wins, and it is never written to the
library.

You can also save a key through the API:

```bash
curl -X PATCH http://127.0.0.1:8000/api/settings \
  -H 'Content-Type: application/json' \
  -d '{"openrouter_api_key": "sk-or-..."}'
```

- Keys are write-only: the API reports only whether a key is set
  (`"has_key": true`), never the key itself. Keys are not logged.
- A saved key is stored in plain text in `library.db` in the data folder, the
  same way it would sit in a `.env` file. Phemius keeps that folder private to
  the account that runs it: the folder is `0700` and `library.db` (with its
  `-wal` and `-shm` files) is `0600`, so other local users cannot read the
  database or the audio. If an existing library is readable by others, startup
  tightens it and logs `library_permissions_tightened` with the paths. A watched
  folder is never changed. On Windows, file modes are not applied; rely on the
  folder's location in your user profile.
- The same works for `openai_api_key` and `script_api_key`.
- Send `{"openrouter_api_key": null}` to remove a saved key.
- Saving a key also switches the default provider to `openrouter`, unless
  `PHEMIUS_SCRIPT_PROVIDER` says otherwise.

A Settings screen in the web UI is planned; it uses the same API.

## Voices

Voice ids are namespaced by engine, for example `kokoro:af_heart`. Wherever
Phemius accepts a voice (`PHEMIUS_VOICE`, `POST /api/docs/{id}/audio`), a bare
id such as `af_heart` is also accepted and namespaced with the configured
engine.

| Engine (`PHEMIUS_TTS`) | Voices |
| --- | --- |
| `kokoro` (default) | `kokoro:af_heart` (default), `af_bella`, `af_nicole`, `af_sarah`, `af_sky`, `am_adam`, `am_michael`, `bf_emma`, `bf_isabella`, `bm_george`, `bm_lewis`. The first letter is the accent (American or British), the second the gender. |
| `piper` | `piper:en_US-joe-medium` (default), `en_US-lessac-medium` (non-commercial use only), `en_GB-cori-medium`, `en_GB-northern_english_male-medium`. See [Piper](#piper). |
| `openai_speech` | The names in `PHEMIUS_OPENAI_SPEECH_VOICES`, by default OpenAI's `alloy` (default), `ash`, `coral`, `echo`, `fable`, `nova`, `onyx`, `sage` and `shimmer`, for example `openai_speech:nova` |
| `elevenlabs` | The voice ids in `PHEMIUS_ELEVENLABS_VOICES`, by default the premade voices George (`elevenlabs:JBFqnCBsd6RMkjVDRZzb`, default) and Sarah (`elevenlabs:EXAVITQu4vr4xnSDxMaL`) |
| `stub` | `stub:silent`, silent audio for testing |

`GET /api/config` lists the voices of the configured engine (`voices`), the
default voice (`default_voice`) and whether the engine is ready
(`tts_status`), for example:

```json
"tts_status": {"is_ready": false, "message": "Kokoro is not installed.", "hint": "Run `uv sync --extra kokoro`, or set PHEMIUS_TTS=stub to test."}
```

### Piper

Piper is small and fast and runs on low-power machines such as a small VPS or a
Raspberry Pi. It does not need Kokoro. Install it and select it:

```bash
uv sync --extra piper
PHEMIUS_TTS=piper make run backend
```

Each voice is about 63 MB. A voice downloads the first time you narrate with it,
into `<data folder>/voices/piper`, and its SHA-256 checksum is verified before
it is kept; a failed or corrupted download leaves no file behind. `tts_status`
reports `Piper is not installed.`, `Piper voice not downloaded yet.` or
`Piper is ready.`

The voices come from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices).
Each was trained on a dataset with its own license; check it before you use the
audio beyond personal listening:

| Voice | Accent | Dataset license |
| --- | --- | --- |
| `piper:en_US-joe-medium` (default) | American English, male | CC0 |
| `piper:en_US-lessac-medium` | American English, female | [Blizzard 2013 Lessac license](https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html): **non-commercial use only** |
| `piper:en_GB-cori-medium` | British English, female | Public domain (LibriVox recordings) |
| `piper:en_GB-northern_english_male-medium` | British English, male | [CC BY-SA 4.0](http://www.openslr.org/83/) |

The `piper-tts` package itself is licensed GPL-3.0-or-later, so it is an
optional extra and is never bundled with the default install or the Docker image
(see ADR-003 in [docs/architecture.md](docs/architecture.md)).

### Hosted voices

Hosted voices send the script, never the source document, to the provider.
Kokoro stays the default; choose a hosted engine with `PHEMIUS_TTS`.

**OpenAI or an OpenAI-compatible speech server** (`openai_speech`) calls
`POST {PHEMIUS_OPENAI_SPEECH_BASE_URL}/audio/speech`:

```bash
# OpenAI
PHEMIUS_TTS=openai_speech PHEMIUS_OPENAI_SPEECH_API_KEY=sk-... make run

# A self-hosted server that needs no key
PHEMIUS_TTS=openai_speech \
PHEMIUS_OPENAI_SPEECH_BASE_URL=http://127.0.0.1:8880/v1 \
PHEMIUS_OPENAI_SPEECH_MODEL=kokoro \
PHEMIUS_OPENAI_SPEECH_VOICES=af_heart,am_adam \
make run
```

The server must support `"response_format": "wav"`. `tts_status` is ready when
`{base URL}/models` answers; a server that does not list models (404) counts as
reachable.

**ElevenLabs** (`elevenlabs`) uses the `eleven_multilingual_v2` model:

```bash
PHEMIUS_TTS=elevenlabs ELEVENLABS_API_KEY=... \
PHEMIUS_ELEVENLABS_VOICES=JBFqnCBsd6RMkjVDRZzb,your-cloned-voice-id make run
```

Voice ids come from the ElevenLabs voice library ("Copy voice ID"). `tts_status`
is ready when the key can read the first voice in the list.

How long scripts are narrated:

- Each request stays under the provider's limit: 4,096 characters for
  `openai_speech`, 5,000 for `elevenlabs` (below its 10,000 limit, so a failed
  request is cheaper to retry). The script is split at paragraph and sentence
  boundaries; only a single sentence longer than the limit is split between
  words.
- The parts are joined into one WAV file without ffmpeg: OpenAI-compatible
  servers return WAV and ElevenLabs returns raw 24 kHz PCM. `PHEMIUS_FORMAT`
  then converts the file as for any engine.
- A bad key, an exhausted quota or a rate limit fails the audio with a hint, for
  example `ElevenLabs returned 401. Your ElevenLabs credits are used up; upgrade
  or wait for the reset.` Provider messages are not shown, because they can
  echo part of the key.

The API keys are write-only, like the OpenRouter key: save them with
`PATCH /api/settings` (`openai_speech_api_key`, `elevenlabs_api_key`) or set
them as environment variables. They are never returned or logged.

## Watched folder

Set `PHEMIUS_WATCH_DIR` to have Phemius import documents from a folder:

```bash
PHEMIUS_WATCH_DIR=~/Documents/listen make run
```

- The folder is created if it does not exist, and subfolders are included.
- On startup, every supported file already in the folder is imported.
- While the server runs, new and changed files are imported about a second after
  they are written. New files get their audio generated automatically.
- Hidden files (names starting with `.`) and unsupported types are skipped.
- A document is identified by its path. Editing a file adds a new version of the
  same document; earlier versions and their audio stay in the library. Saving a
  file without changing its text adds nothing.
- `PHEMIUS_WATCH_ON_CHANGE` decides what happens when a file changes: `mark`
  (default) only marks the document as changed (`is_changed` in `GET /api/docs`)
  so you can generate audio when the edit is finished; `regenerate` generates
  audio for every new version, which spends model credits on each save.
- The folder is read at startup, so restart after changing it, including when
  you change a saved `watch_dir` setting.

## Access from other devices

Phemius has no user accounts. Anyone who can reach its port can read and delete
the library, so `PHEMIUS_ACCESS_MODE` decides who can reach it:

| Mode | Listens on | Access token |
| --- | --- | --- |
| `local` (default) | `127.0.0.1`, this computer only | Not needed |
| `network` | `0.0.0.0`, every device on your network | Required |
| `proxy` | `127.0.0.1`, for a reverse proxy on the same computer that adds HTTPS or a domain; trusts its `X-Forwarded-*` headers | Required |

`phemius serve` (and `make run`) pick the address from the mode, so start the
server through them rather than calling `uvicorn` with your own `--host`. The
mode is read when the server starts; restart after changing it.

Send the token with every API request as `Authorization: Bearer <token>`;
without it, requests get `401 unauthorized`. An `<audio>` element cannot send
headers, so `GET /api/audio/{id}/file` also accepts `?token=<token>`.
`GET /api/health` and the UI files load without a token, and the UI asks for the
token on the first `401`. Phemius stores only a hash of the token, so it can
never show it again.

### Set your own token (recommended for deployments)

Set `PHEMIUS_ACCESS_TOKEN` to a long random value, at least 16 characters, for
example in a `.env` file passed to Docker:

```bash
echo "PHEMIUS_ACCESS_TOKEN=$(openssl rand -hex 32)" >> .env
```

The variable wins over any generated token, which stops working. Nothing is
printed. To rotate it, change the variable and restart. While it is set,
`POST /api/access/token` refuses with `409 setting_locked`. A shorter value
stops the server from starting with `PHEMIUS_ACCESS_TOKEN must be at least 16
characters.`

### Generated token

Without `PHEMIUS_ACCESS_TOKEN`, the first start in `network` or `proxy` mode
creates a `phm_...` token and prints it once:

```bash
PHEMIUS_ACCESS_MODE=network make run backend
# Phemius access token (shown once, save it now): phm_...
```

To replace it, call `POST /api/access/token` with the current one. The response
holds the new token, and the old one stops working at once. If you lost it,
either set `PHEMIUS_ACCESS_TOKEN` and restart, or restart in `local` mode, call
`POST /api/access/token` from the same computer, and restart in your previous
mode.

## Configuration

Each setting is resolved in this order:

1. **Environment variable**, if set to a non-empty value.
2. **Saved setting**, from `PATCH /api/settings`.
3. **Default.**

A setting fixed by an environment variable is locked: `GET /api/settings`
reports it with `"source": "env"` and `"is_locked": true`, and `PATCH` refuses to
change it with `409 setting_locked`. Unset the variable and restart to manage it
from the API (and later the UI). Environment variables are read when the server
starts; saved settings apply on their next use without a restart (except
`watch_dir`).

| Variable | Setting key | Default | Description |
| --- | --- | --- | --- |
| `PHEMIUS_DATA_DIR` | environment only | `~/.phemius` | Library folder. Holds `library.db` (SQLite, including saved settings and keys) and `audio/`. Created on startup, readable only by its owner. |
| `PHEMIUS_LOG_LEVEL` | environment only | `info` | Log level: `debug`, `info`, `warning` or `error`. |
| `PHEMIUS_SCRIPT_PROVIDER` | `script_provider` | `openrouter` when an OpenRouter key is configured, otherwise `offline` | Who categorizes and writes scripts: `offline`, `openrouter`, `openai`, `openai_compatible` or `ollama`. See [Script model](#script-model). |
| `PHEMIUS_MODEL` | `model` | `anthropic/claude-sonnet-4.5` | Model name sent to the script provider, for example an OpenRouter slug. Set it when you use `openai` or `openai_compatible`. |
| `PHEMIUS_SCRIPT_MAX_TOKENS` | `script_max_tokens` | `8000` | Maximum tokens a model may write for one script. A positive whole number. |
| `OPENROUTER_API_KEY` | `openrouter_api_key` | not set | OpenRouter API key. Write-only through the API. See [API keys](#api-keys). |
| `OPENAI_API_KEY` | `openai_api_key` | not set | OpenAI API key, used by the `openai` provider. Write-only through the API. |
| `PHEMIUS_SCRIPT_BASE_URL` | `script_base_url` | not set | Base URL of an OpenAI-compatible server, for example `http://localhost:1234/v1`. Used by the `openai_compatible` provider. Must start with `http://` or `https://`. |
| `PHEMIUS_SCRIPT_API_KEY` | `script_api_key` | not set | API key for the `openai_compatible` server, if it needs one. Write-only through the API. |
| `PHEMIUS_OLLAMA_URL` | `ollama_url` | `http://localhost:11434` | Ollama server address. Used only by the `ollama` provider. |
| `PHEMIUS_OLLAMA_MODEL` | `ollama_model` | `llama3.2` | Ollama model name, as shown by `ollama list`. |
| `PHEMIUS_OLLAMA_TIMEOUT` | `ollama_timeout` | `600` | Seconds to wait for one Ollama reply. A positive whole number. |
| `PHEMIUS_TTS` | `voice_engine` | `kokoro` | Voice engine: `kokoro`, `piper`, `openai_speech`, `elevenlabs` or `stub` (silent audio, no model download). See [Voices](#voices). |
| `PHEMIUS_VOICE` | `default_voice` | the engine's first voice (`kokoro:af_heart`) | Default voice for new audio. A voice id of the configured engine; see [Voices](#voices). |
| `PHEMIUS_OPENAI_SPEECH_BASE_URL` | `openai_speech_base_url` | `https://api.openai.com/v1` | Base URL of an OpenAI-compatible speech server. See [Hosted voices](#hosted-voices). |
| `PHEMIUS_OPENAI_SPEECH_API_KEY` | `openai_speech_api_key` | not set | API key for the speech server; leave unset for a server that needs none. Write-only through the API. |
| `PHEMIUS_OPENAI_SPEECH_MODEL` | `openai_speech_model` | `tts-1` | Speech model name sent to the server. |
| `PHEMIUS_OPENAI_SPEECH_VOICES` | `openai_speech_voices` | `alloy,ash,coral,echo,fable,nova,onyx,sage,shimmer` | Comma-separated voice names the server offers; the first is the engine's default. |
| `ELEVENLABS_API_KEY` | `elevenlabs_api_key` | not set | ElevenLabs API key. Write-only through the API. |
| `PHEMIUS_ELEVENLABS_VOICES` | `elevenlabs_voices` | `JBFqnCBsd6RMkjVDRZzb,EXAVITQu4vr4xnSDxMaL` | Comma-separated ElevenLabs voice ids; the first is the engine's default. |
| `PHEMIUS_WATCH_DIR` | `watch_dir` | not set (no folder watched) | Folder to import documents from. See [Watched folder](#watched-folder). |
| `PHEMIUS_ACCESS_MODE` | `access_mode` | `local` | Who can reach the server: `local`, `network` or `proxy`. See [Access from other devices](#access-from-other-devices). Applies on the next start. |
| `PHEMIUS_ACCESS_TOKEN` | environment only | not set (a token is generated) | Access token for `network` and `proxy` modes, at least 16 characters. Write-only: never shown or logged. See [Set your own token](#set-your-own-token-recommended-for-deployments). |
| `PHEMIUS_WATCH_ON_CHANGE` | `watch_on_change` | `mark` | What a changed watched file does: `mark` (mark the document as changed) or `regenerate` (generate audio for the new version). |
| `PHEMIUS_FORMAT` | `output_format` | `wav` | Audio file format: `wav`, `m4a`, `mp4` or `mp3`. Formats other than WAV need `ffmpeg` on your `PATH`; without it, Phemius keeps the WAV file. |

Invalid values are reported as follows:

| Problem | What happens |
| --- | --- |
| A value of the wrong type or outside the allowed list, for example `PHEMIUS_FORMAT=ogg` or `PHEMIUS_SCRIPT_MAX_TOKENS=abc` | The server does not start. The log shows `Setting output_format has an invalid value.` (the setting key from the table) and `Application startup failed`. Through `PATCH /api/settings`, the same values are rejected with `422`. |
| Unknown `PHEMIUS_TTS` | The server starts and logs `voice_engine_not_ready`. Creating audio fails with `Unknown voice engine '...'. Set PHEMIUS_TTS to one of: kokoro, stub, openai_speech, elevenlabs, piper.` |
| `PHEMIUS_VOICE` that the engine does not offer | Creating audio fails with `PHEMIUS_VOICE '...' is not a kokoro voice.` and a list of valid ids. |
| Unknown `PHEMIUS_SCRIPT_PROVIDER` | Categorizing falls back to the offline rules; scripts fail with `Unknown script provider '...'.` and the valid names. |
| `PHEMIUS_SCRIPT_PROVIDER=openrouter` without a key | Scripts fail with `OpenRouter needs an API key.` |

`make run` also accepts `PORT` (default `8000`) as a make variable for the API;
the address comes from `PHEMIUS_ACCESS_MODE`. The UI dev server always proxies to
`127.0.0.1:8000`, so change `PORT` only together with `make run backend` and a
built UI.

## API

Every endpoint is listed with its schema in the interactive docs at
<http://127.0.0.1:8000/docs>.

| Method and path | Description |
| --- | --- |
| `GET /api/health` | `{"status": "ok"}` when the database is readable and the data folder is writable; `503` otherwise |
| `GET /api/config` | Tones, voices, default voice, voice engine and its `tts_status`, script provider, model, last categorizing error, watched folder |
| `GET /api/settings` | Every setting with its value, `source` (`env`, `saved` or `default`) and `is_locked`; secrets only as `has_key` |
| `PATCH /api/settings` | Save some settings (only the fields sent; `null` removes a saved value). `409` if a field is locked by an environment variable, `422` for invalid values |
| `GET /api/docs` | Library: all documents, newest first, each with its audio |
| `POST /api/docs` | Upload one or more files (multipart field `files`). Uploading a changed file with the same name adds a version. Generates audio unless `?auto_audio=false` |
| `GET /api/docs/{id}` | One document's latest version, including its extracted text |
| `GET /api/docs/{id}/versions` | The document's versions, newest first, each with its audio. Paginated with `?limit=` (default 25, max 100) and `?offset=` |
| `POST /api/docs/{id}/audio` | Generate another audio. Body: `{"tone": "teacher", "voice": "kokoro:bf_emma"}`; both fields optional |
| `GET /api/audio/{id}` | One audio, including its status, script and error |
| `GET /api/audio/{id}/file` | The audio file, once its status is `done`. Accepts `?token=` in `network` and `proxy` modes |
| `POST /api/access/token` | Replace the access token and return the new one, `{"token": "phm_..."}`. The old token stops working at once. `409 setting_locked` while `PHEMIUS_ACCESS_TOKEN` is set |

Errors share one shape:

```json
{
  "detail": "Some settings are set by environment variables.",
  "code": "setting_locked",
  "hint": "Unset the variable and restart to change it here.",
  "errors": [{"field": "model", "message": "Set by environment variable PHEMIUS_MODEL"}]
}
```

`hint` and `errors` appear only when Phemius has something to add.

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

`GET /api/config` shows whether the voice engine is ready (`tts_status`) and the
last categorizing error (`llm_error`).

### "Kokoro is not installed"

The server logs `voice_engine_not_ready` at startup, `GET /api/config` reports
it in `tts_status`, and audio fails with:

```text
Kokoro is not installed. Run `uv sync --extra kokoro`, or set PHEMIUS_TTS=stub to test.
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

### `npm` errors during `make install`

Check `node --version`. The UI expects Node 22 (`frontend/.nvmrc`); with
[nvm](https://github.com/nvm-sh/nvm), run `nvm use` inside `frontend/`. If you do
not need the UI, use `make install backend` and `make run backend`.

### `http://127.0.0.1:8000/` shows `Not Found`

The UI has not been built. Open the dev server at <http://localhost:5173>
instead, or run `make build` and restart the server.

### Port already in use

```text
ERROR:    [Errno 48] error while attempting to bind on address ('127.0.0.1', 8000): address already in use
```

Another process (often another Phemius) is using port 8000. Find and stop it:

```bash
lsof -i :8000
```

On Linux the error number is 98 instead of 48. If port 5173 is taken, Vite
moves to the next free port and prints the URL to open.

### The server does not start after setting a variable

Look for `Setting <key> has an invalid value.` in the output. Find the variable
for that key in the [configuration table](#configuration) and fix or unset it.

### Audio stays WAV when I set `PHEMIUS_FORMAT`

ffmpeg is not on your `PATH`. Install it (for example `brew install ffmpeg` or
`sudo apt install ffmpeg`) and restart the server.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the workflow and
[docs/architecture.md](docs/architecture.md) for how Phemius is built and the
decisions behind it.

## License

Apache-2.0. See [LICENSE](LICENSE).

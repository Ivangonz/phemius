# Phemius in one image: the UI is built with Node in the first stage, and the
# final image runs only Python 3.12, with no Node.
#
#   docker build -t phemius .                             # with Kokoro and ffmpeg
#   docker build -t phemius:slim \
#     --build-arg WITH_KOKORO=false --build-arg WITH_FFMPEG=false .   # small image
#
# WITH_KOKORO=false leaves out Kokoro and PyTorch; use a hosted voice
# (PHEMIUS_TTS=openai_speech or elevenlabs) or the silent stub with it.
# WITH_FFMPEG=false leaves out ffmpeg, so audio stays WAV (PHEMIUS_FORMAT).

# --- UI: keep the Node major version in step with frontend/.nvmrc ---
FROM node:22-slim AS ui
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Vite writes to ../src/phemius/static, that is /app/src/phemius/static.
RUN npm run build

# --- Python environment, built with uv into /opt/venv ---
FROM python:3.12-slim AS build
ARG WITH_KOKORO=true
# misaki (Kokoro's English phonemizer) loads this spaCy model and would try to
# pip-install it on the first narration, which fails in a uv environment.
ARG SPACY_MODEL_URL=https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
ARG SPACY_MODEL_SHA256=1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85
COPY --from=ghcr.io/astral-sh/uv:0.10.4 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app

# Dependencies first, so a code change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project \
      $([ "$WITH_KOKORO" = "true" ] && echo --extra kokoro)

COPY src/ src/
COPY --from=ui /app/src/phemius/static src/phemius/static
RUN uv sync --locked --no-dev --no-editable \
      $([ "$WITH_KOKORO" = "true" ] && echo --extra kokoro)
RUN if [ "$WITH_KOKORO" = "true" ]; then \
      echo "en-core-web-sm @ ${SPACY_MODEL_URL} --hash=sha256:${SPACY_MODEL_SHA256}" \
        > /tmp/spacy-model.txt \
      && uv pip install --python /opt/venv/bin/python --no-deps --require-hashes \
        -r /tmp/spacy-model.txt; \
    fi

# --- Runtime: Python 3.12, the virtualenv and an unprivileged user ---
FROM python:3.12-slim AS runtime
ARG WITH_FFMPEG=true
RUN if [ "$WITH_FFMPEG" = "true" ]; then \
      apt-get update \
      && apt-get install --yes --no-install-recommends ffmpeg \
      && rm -rf /var/lib/apt/lists/*; \
    fi \
    && groupadd --gid 1000 phemius \
    && useradd --uid 1000 --gid phemius --create-home phemius \
    && mkdir /data \
    && chown phemius:phemius /data \
    && chmod 0700 /data

COPY --from=build /opt/venv /opt/venv

# Network mode listens on 0.0.0.0 and requires the access token, so the
# published port is never open without one. The Kokoro voice model downloads
# into the data folder, so it survives a new container.
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PHEMIUS_DATA_DIR=/data \
    PHEMIUS_ACCESS_MODE=network \
    HF_HOME=/data/cache/huggingface

USER phemius
WORKDIR /home/phemius
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

ENTRYPOINT ["phemius", "serve"]

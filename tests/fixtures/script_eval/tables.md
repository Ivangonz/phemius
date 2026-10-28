# Choosing a voice engine

Phemius supports several voice engines. They differ in quality, speed and what
they need to run.

| Engine | Runs offline | Quality | Notes |
|--------|:------------:|---------|-------|
| Kokoro | yes | high | Default; downloads a model on first use |
| Piper | yes | medium | Fast on small machines |
| ElevenLabs | no | very high | Needs an API key and credits |

For most people the default is the right choice. Pick Piper on a small server
and ElevenLabs when you want the most natural voice and do not mind paying.

| Setting | Default |
| --- | --- |
| Speed | 1.0 |
| Format | m4a |

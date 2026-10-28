# Running the worker locally

The worker processes the job queue. You can start it from a checkout in two
commands.

```bash
uv sync
uv run worker --queue default --concurrency 2
```

The worker reads its settings from the environment. A minimal configuration
looks like this:

```python
def load_settings() -> dict[str, str]:
    url = os.environ.get("QUEUE_URL", "https://queue.example.com")
    return {"queue_url": url, "log_level": "info"}
```

To check that it is running, list the active jobs:

    uv run worker status

If the status command hangs, the queue database is probably locked by another
process. Stop the other process and try again.

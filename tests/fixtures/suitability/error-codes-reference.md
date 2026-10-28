# Error code reference

Every API error returns one of these codes.

| Code | HTTP status | Meaning | Retry |
| --- | --- | --- | --- |
| `invalid_input` | 400 | A field failed validation | No |
| `unauthorized` | 401 | The access token is missing or wrong | No |
| `not_found` | 404 | The document or audio does not exist | No |
| `setting_locked` | 409 | An environment variable fixes the setting | No |
| `model_error` | 502 | The script model provider failed | Yes |
| `voice_error` | 502 | The voice engine failed | Yes |
| `rate_limited` | 429 | Too many requests to the provider | Yes |
| `timeout` | 504 | The provider took too long | Yes |
| `internal_error` | 500 | An unexpected failure | Yes |

## Limits

| Limit | Value |
| --- | --- |
| Page size | 25 |
| Maximum page size | 100 |
| Script characters | 40000 |

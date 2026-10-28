# Configuring the API gateway

The API gateway terminates TLS and forwards requests to the backend over HTTP.
Its settings live in `gateway.yaml`, next to the `README.md` in the repository
root.

Set `max_body_size` to limit uploads, and point `upstream_url` at the service.
The CLI reloads the file without a restart when you run `gateway reload`.

For SSO, the gateway speaks OIDC. Register it with your IdP and copy the client
ID into `.env`. Keep the client secret out of version control.

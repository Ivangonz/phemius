# Deploying the Billing Service

This guide explains how to deploy the billing service to staging.

## Prerequisites

1. Install the `kubectl` CLI.
2. Get access to the **staging** cluster.

## Steps

1. Run `make build` to produce the container image.
2. Run `make deploy ENV=staging`.
3. Verify with `kubectl get pods -n billing`.

```bash
make deploy ENV=staging
```

See the [runbook](https://example.com/runbook) if pods crash.

# Security policy

## Supported version

The latest `main` branch is supported. This is an educational portfolio project and has no
production service-level commitment.

## Reporting

Do not publish a suspected vulnerability in an issue. Use GitHub's private vulnerability
reporting for this repository when available, or contact the repository owner privately through
the profile contact channel.

Include the affected revision, reproduction steps, expected impact, and a minimal proof of
concept that contains no real credentials or sensitive data.

## Security boundaries

- JSON model artifacts are data, not executable Python objects; their digest, schema, dimensions,
  finite numeric values, and resolved path are checked before use.
- Administrative mutations require a configured token and constant-time comparison. The example
  is not a substitute for production identity, authorization, rotation, or transport controls.
- Prediction logs store identifiers, model provenance, probabilities, decisions, and latency—not
  raw observations.
- Containers run non-root with privilege escalation disabled; Kubernetes also drops capabilities,
  disables automatic service-account credentials, and uses a read-only root filesystem.
- Dependency versions and automation actions are pinned and continuously reviewed.

See [docs/risk-register.md](docs/risk-register.md) for residual risks and owners.

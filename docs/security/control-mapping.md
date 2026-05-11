# Banking Control Mapping

This project aligns technical controls with core banking compliance frameworks.

## PCI DSS
- Strong authentication and session control for privileged operations.
- Signed transaction intents and replay prevention.
- Continuous risk telemetry for anomaly response.

## GDPR
- Data minimization in DSAR exports (raw behavioral payloads redacted by default).
- Auditable access and export activity logs.
- Configurable retention tags for evidence records.

## SOC 2
- Security event evidence trail with action/status/rationale.
- CI security gates for dependency and static analysis checks.
- Session context verification to reduce account takeover risk.

## ISO 27001
- Policy-driven operational safeguards via configuration.
- Security monitoring and incident evidence generation.
- Structured documentation for controls and response processes.

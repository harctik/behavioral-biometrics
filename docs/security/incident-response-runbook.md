# Incident Response Runbook

## 1. Detect
- Monitor `risk_level`, `risk_score`, `step_up_recommended`, and context mismatch events.
- Trigger alerts for repeated `transaction_assess` blocks or anomaly spikes.

## 2. Triage
- Pull evidence from `/api/session/trust-timeline` and `/api/compliance/dsar`.
- Classify severity based on session compromise confidence and transaction risk.

## 3. Contain
- End active sessions (`/api/logout`) for impacted identities.
- Enforce step-up verification for affected users.

## 4. Eradicate
- Review suspicious patterns in `audit_evidence` and `auth_events`.
- Rotate secrets if signature abuse is suspected.

## 5. Recover
- Re-enable safe access with monitored MFA verification.
- Continue heightened monitoring for 24-72 hours.

## 6. Post-Incident
- Document timeline, scope, and corrective actions.
- Add regression tests and update controls where gaps were identified.

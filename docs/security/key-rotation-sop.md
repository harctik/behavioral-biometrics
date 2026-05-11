# Key Rotation SOP

## Scope
- JWT signing secrets
- CSRF token secrets
- Transaction intent signing secrets

## Procedure
1. Generate new secret material in secure secret manager.
2. Deploy with dual-read support where applicable (`JWT_PREVIOUS_SECRET_KEY`).
3. Rotate application instances gradually.
4. Invalidate legacy sessions after grace period.
5. Verify no signature errors in transaction assessment.

## Cadence
- Routine: every 90 days.
- Emergency: immediately after any suspected key exposure.

## Validation
- Confirm auth success rates remain healthy.
- Confirm `transaction_assess` signature verification passes post-rotation.
- Confirm audit evidence logs capture rotation activity.

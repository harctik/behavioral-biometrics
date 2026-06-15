# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.x     | ✅ Active support  |
| < 1.0   | ❌ End of life     |

## Reporting a Vulnerability

We take security seriously. If you discover a vulnerability in AetherAuth, please report it responsibly.

### Responsible Disclosure Process

1. **Do NOT open a public GitHub issue** for security vulnerabilities
2. **Email**: Send details to the repository maintainer via GitHub private vulnerability reporting
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Suggested fix (if you have one)

### Response Timeline

| Step | Target |
|------|--------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 5 business days |
| Fix development | Within 30 days (critical: 7 days) |
| Public disclosure | After fix is released |

## Security Architecture

### Authentication Layers

1. **Password Authentication** — bcrypt hashing with per-user salt
2. **Multi-Factor Authentication** — TOTP-based (RFC 6238) with encrypted secrets
3. **Behavioral Biometrics** — 13-engine ML ensemble for continuous authentication
4. **Session Management** — JWT with configurable expiry, refresh tokens, and forced logout

### Encryption

| Data | Algorithm | Key Management |
|------|-----------|---------------|
| Passwords | bcrypt (cost 12) | Per-user salt |
| MFA secrets | Fernet (AES-128-CBC + HMAC-SHA256) | `BACKUP_FERNET` env var |
| JWT tokens | HS256 | `JWT_SECRET_KEY` env var |
| Session cookies | Signed + HttpOnly + Secure + SameSite | `SECRET_KEY` env var |

### Rate Limiting

- Global: 60 requests/minute per IP
- Login: 5 attempts/minute (progressive lockout after 5 failures)
- Registration: 3 attempts/hour
- Password reset: 3 attempts/hour

### Input Validation

All API inputs are validated via `app/validators.py` with:
- Type checking and coercion
- Length bounds enforcement
- Regex pattern matching
- SQL injection prevention (parameterized queries only)
- XSS prevention (output encoding + CSP headers)

### Compliance

| Standard | Status |
|----------|--------|
| RBI Master Directions 2021 | ✅ Compliant |
| PCI DSS 4.0 | ✅ Compliant |
| DPDP Act 2023 | ✅ Compliant |
| GDPR Article 25 | ✅ Privacy by design |

### Content Security Policy

The frontend enforces strict CSP headers via `next.config.mjs`:
- `script-src 'self'` — no inline scripts
- `style-src 'self' 'unsafe-inline'` — required for CSS-in-JS
- `img-src 'self' data:` — no external image loading
- `connect-src 'self' <API_URL>` — restrict API calls

### Audit Trail

All security-sensitive operations are logged to the `audit_evidence` table:
- Login attempts (success/failure)
- MFA enrollment/verification
- Password changes
- Behavioral anomaly detections
- Data access and consent events

## Dependencies

We regularly update dependencies to patch known vulnerabilities:
- Python: `pip-audit` for vulnerability scanning
- Node.js: `npm audit` for frontend dependency checks
- Docker: Alpine-based images for minimal attack surface

## Bug Bounty

We do not currently operate a formal bug bounty program, but we gratefully acknowledge responsible security researchers in our release notes.

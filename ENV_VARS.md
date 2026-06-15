# Environment Variables Reference

Complete reference for all environment variables used by the Behavioral Biometrics Authentication system.

---

## Frontend (Next.js / Vercel)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | **Yes** (production) | `http://127.0.0.1:5000` | Backend API base URL. Set to your Render deployment URL in production. |
| `NODE_ENV` | No | `development` | `development` \| `production` \| `test` |

---

## Backend (Flask / Render)

### Core Application

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | **Yes** | `dev-secret-key` | Flask secret key. **Must be cryptographically random in production.** |
| `JWT_SECRET_KEY` | **Yes** | `jwt-dev-key` | JWT signing secret. Generate with `python -c "import secrets; print(secrets.token_hex(64))"`. |
| `JWT_PREVIOUS_SECRET_KEY` | No | `""` | Previous JWT secret for zero-downtime key rotation. |
| `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` | No | `30` | JWT access token expiry in minutes. |
| `DEBUG` | No | `false` | Enable Flask debug mode. **Never true in production.** |
| `FLASK_ENV` | No | `development` | `development` \| `production` |
| `PORT` | No | `5000` | HTTP port. Render sets this automatically. |
| `APP_VERSION` | No | `2.0.0` | Application version shown in health endpoint. |

### Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SQLALCHEMY_DATABASE_URI` | **Yes** (production) | `sqlite:///behavioral_auth.db` | PostgreSQL connection string. Format: `postgresql://user:pass@host:port/db` |
| `DATABASE_PATH` | No | `behavioral_auth.db` | SQLite database file path (development only). |

### Redis

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | Recommended | `""` | Redis connection URL for session caching and ensemble score caching. Format: `redis://host:6379/0` |
| `SESSION_CACHE_TTL_SECONDS` | No | `3600` | Session cache TTL in Redis. |

### Security

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CSRF_ENABLED` | No | `true` | Enable CSRF protection. |
| `CSRF_HEADER_NAME` | No | `X-CSRF-Token` | Custom CSRF header name. |
| `HSTS_MAX_AGE` | No | `31536000` | HSTS max-age in seconds (1 year). |
| `REFERRER_POLICY` | No | `strict-origin-when-cross-origin` | Referrer-Policy header value. |
| `CSP_POLICY` | No | _(auto-generated)_ | Custom Content-Security-Policy header. |
| `CORS_ORIGINS` | **Yes** (production) | `*` | Comma-separated list of allowed CORS origins. Example: `https://your-app.vercel.app` |
| `IP_ALLOWLIST` | No | `""` | Comma-separated IPs to allowlist. Empty = allow all. |
| `IP_DENYLIST` | No | `""` | Comma-separated IPs to block. |
| `TXN_SIGNING_KEY` | Recommended | `""` | HMAC key for transaction signing. |
| `TXN_SIGNING_PREVIOUS_KEY` | No | `""` | Previous transaction signing key for rotation. |
| `TRANSACTION_SIGNING_REQUIRED` | No | `false` | Enforce transaction HMAC signatures. |
| `BACKUP_FERNET` | No | `""` | Backup Fernet encryption key. |

### Risk Thresholds

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RISK_HIGH_THRESHOLD` | No | `0.65` | Risk score threshold for HIGH classification. |
| `RISK_MEDIUM_THRESHOLD` | No | `0.35` | Risk score threshold for MEDIUM classification. |
| `STEP_UP_RISK_SCORE_THRESHOLD` | No | `0.6` | Risk score that triggers step-up authentication. |

### Session Context

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SESSION_CONTEXT_STRICT` | No | `true` | Enforce strict session context validation. |
| `TRUST_TIMELINE_DEFAULT_WINDOW_MINUTES` | No | `30` | Default trust timeline window. |
| `TRUST_TIMELINE_MAX_WINDOW_MINUTES` | No | `180` | Maximum allowed trust timeline window. |

### Email (Password Reset)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAIL_BACKEND` | No | `smtp` | `smtp` \| `ses` \| `resend` |
| `MAIL_SERVER` | No | `""` | SMTP server hostname. |
| `MAIL_PORT` | No | `587` | SMTP server port. |
| `MAIL_USE_TLS` | No | `true` | Use TLS for SMTP. |
| `MAIL_USERNAME` | No | `""` | SMTP username. |
| `MAIL_PASSWORD` | No | `""` | SMTP password. |
| `MAIL_DEFAULT_SENDER` | No | `""` | Default sender email address. |
| `AWS_REGION` | No | `""` | AWS region for SES. |
| `RESEND_API_KEY` | No | `""` | Resend API key. |
| `RESET_URL_BASE` | No | `""` | Base URL for password reset links. |

### Access Control

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ADMIN_USERNAMES` | No | `""` | Comma-separated admin usernames. |
| `ANALYST_USERNAMES` | No | `""` | Comma-separated analyst usernames. |

---

## Production Deployment Checklist

> ⚠️ **CRITICAL**: Ensure all **Required** variables are set before deploying to production.

1. ✅ Generate unique `SECRET_KEY` and `JWT_SECRET_KEY`
2. ✅ Set `SQLALCHEMY_DATABASE_URI` to PostgreSQL (not SQLite)
3. ✅ Set `CORS_ORIGINS` to your Vercel frontend URL
4. ✅ Set `NEXT_PUBLIC_API_URL` to your Render backend URL
5. ✅ Set `DEBUG=false` and `FLASK_ENV=production`
6. ✅ Configure `REDIS_URL` for session caching
7. ✅ Review and set risk thresholds for your use case

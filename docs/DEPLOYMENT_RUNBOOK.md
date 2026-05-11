# Deployment Runbook — BehaviorGuard

## Pre-flight Checklist

### 1. Environment Variables (REQUIRED)

Generate and set these before starting the container:

```bash
# Generate all secrets at once
python -c "import secrets; print(f'SECRET_KEY={secrets.token_urlsafe(64)}')"
python -c "import secrets; print(f'JWT_SECRET_KEY={secrets.token_urlsafe(64)}')"
python -c "import secrets; print(f'TXN_SIGNING_KEY={secrets.token_urlsafe(64)}')"
python -c "from cryptography.fernet import Fernet; print(f'BACKUP_FERNET={Fernet.generate_key().decode()}')"
```

The application **will refuse to start** in production if:
- `SECRET_KEY` starts with `dev-`
- `JWT_SECRET_KEY` starts with `dev-`
- `TXN_SIGNING_KEY` starts with `dev-`
- `RATELIMIT_STORAGE_URI` is `memory://` or empty

### 2. Redis (REQUIRED for production)

Redis is required for:
- Rate limiting (Flask-Limiter)
- JWT blocklist
- Nonce replay protection
- Session cache
- Password reset token cache

```bash
# Verify Redis is reachable
redis-cli -u redis://your-redis-host:6379 ping
```

Set in `.env`:
```
REDIS_URL=redis://your-redis-host:6379/0
RATELIMIT_STORAGE_URI=redis://your-redis-host:6379/0
```

### 3. Database

SQLite is the default but is **NOT recommended for multi-instance deployments**.
For production, consider PostgreSQL and update `DATABASE_PATH` or `SQLALCHEMY_DATABASE_URI`.

```bash
# Apply all Alembic migrations
alembic upgrade head
```

Or seed the database for demo:
```bash
python seed_data.py --reset
```

---

## Docker Deployment

### Build

```bash
docker build -t behaviorguard:latest .
```

### Run

```bash
docker run -d \
  --name behaviorguard \
  -p 5000:5000 \
  -v ./database:/app/database \
  -v ./models:/app/models \
  --env-file .env \
  behaviorguard:latest
```

### Docker Compose

```bash
docker compose up -d
```

Verify:
```bash
curl -s http://localhost:5000/api/v1/auth/csrf-token | jq .
```

---

## Monitoring

### Health Check

```bash
# Application health
curl http://localhost:5000/api/v1/health

# Swagger docs
open http://localhost:5000/api/v1/
```

### Key Metrics to Watch

| Metric | Source | Alert Threshold |
|--------|--------|----------------|
| Auth latency | App logs (`duration_ms`) | >500ms p95 |
| Failed login rate | `auth_events` table | >20% of total in 5min window |
| Lockout events | `auth_events` (type=`account_locked`) | Any spike |
| Behavioral anomaly rate | `behavioral_data` (anomaly_score) | >30% sessions flagged |
| Model drift | `model_metadata` (drift_detected) | Any `true` |
| Redis connection | Flask-Limiter logs | Any `fallback to memory` |

### Log Files

- Application: `behavioral_auth.log` (RotatingFileHandler, 10MB × 5 backups)
- Docker: `docker logs behaviorguard`
- Structured format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

---

## Rollback Procedure

1. **Stop the new container:** `docker compose down`
2. **Restore DB backup:** `cp database/auth_system.db.bak database/auth_system.db`
3. **Deploy previous image:** `docker compose up -d --force-recreate`
4. **Verify:** `curl http://localhost:5000/api/v1/health`

---

## Secret Rotation

### JWT Secret Rotation (Zero-Downtime)

1. Set `JWT_PREVIOUS_SECRET_KEY` to the current `JWT_SECRET_KEY`
2. Generate and set a new `JWT_SECRET_KEY`
3. Restart the application
4. Wait for all existing tokens to expire (15 min for access, 30 days for refresh)
5. Remove `JWT_PREVIOUS_SECRET_KEY`

### Transaction Signing Key Rotation

Same pattern using `TXN_SIGNING_KEY` and `TXN_SIGNING_PREVIOUS_KEY`.

---

## Frontend Deployment

The Next.js frontend is built separately:

```bash
cd frontend
npm ci
npm run build
# Deploy the .next/standalone output or use a CDN for static assets
```

Configure `next.config.ts` rewrites to proxy `/api/v1/*` to the Flask backend.

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ValueError: SECRET_KEY cannot use a dev default` | Using default secrets in production | Generate proper secrets (see above) |
| `Rate limiter fallback to memory` | Redis not available | Start Redis, set `RATELIMIT_STORAGE_URI` |
| `TemplateNotFound` | Legacy Flask routes still active | Routes were removed; ensure latest code is deployed |
| `sqlite3.OperationalError: no such column: salt` | Migration 004 not applied | Run `alembic upgrade head` or `python -c "..."` migration script |
| Login succeeds when account should be locked | UTC vs local time mismatch | Fixed in latest code (DB-side comparison) |

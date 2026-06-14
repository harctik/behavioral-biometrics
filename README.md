Comprehensive Project Architecture Overview
1. Directory Structure and Purpose
Root-Level Directories
Directory	Purpose
app/	Python Flask Backend - Core application logic, API endpoints, ML models
frontend/	Next.js Frontend - React-based enterprise banking UI
tests/	Test Suite - Comprehensive test coverage (pytest + Locust load testing)
alembic/	Database Migrations - Schema versioning for PostgreSQL
database/	SQLite Data Store - Local development database (auth_system.db)
docs/	Documentation - Architecture, deployment runbooks, security docs
helm/	Kubernetes Helm Charts - Production deployment manifests
models/	Saved ML Models - Trained model storage directory
report_diagrams_png/	Architecture Diagrams - System DFD, ER diagrams, flowcharts
.github/	CI/CD Workflows - GitHub Actions for automated testing
---
2. Key Configuration Files
File	Purpose
run.py	Entry Point - Creates Flask app using factory pattern
app/config.py	Settings Management - Pydantic-based config (270+ settings) for JWT, database, ML, security
requirements.txt	Core Dependencies - Flask, ML libs, database drivers, security packages
requirements-dev.txt	Dev Dependencies - Testing, linting tools
requirements-ml.txt	ML Extra Dependencies - Advanced ML libraries
pyproject.toml	Project Metadata - Poetry-style config
docker-compose.yml	Multi-Container Setup - Web, Redis, PostgreSQL, Celery worker
.pre-commit-config.yaml	Git Hooks - Code quality enforcement
Dockerfile	Container Image - Multi-stage build for production
---
## 3. Entry Points and Application Factory
### Main Entry Points
1. **`run.py`** - The primary run script:
   ```python
   from app.app_impl import create_app
   app = create_app(env)  # env: "development", "production", "testing"
   ```
2. **`app/app.py`** - WSGI compatibility shim (for deployment tools expecting `app.app:app`)
### Application Factory: `app/app_impl.py`
The `create_app(env)` function is the core factory that:
- **Configures Flask** with settings from `app/config.py`
- **Sets up JWT** with key rotation support (current + previous keys)
- **Initializes Rate Limiter** (Flask-Limiter with Redis backend)
- **Creates Flask-RESTX API** with OpenAPI/Swagger docs at `/api/v1/`
- **Registers 14 API Namespaces** (auth, session, behavioral, transaction, admin, compliance, banking, health, webhooks, user, notifications, beneficiaries, investments, cards)
- **Attaches Middleware Stack**:
  - IP Allowlist/Denylist enforcement
  - HTTPS redirection (production)
  - Request correlation IDs
  - Structured request/response logging
  - CSRF token validation
  - Security headers (HSTS, CSP, X-Frame-Options)
  - CORS handling
- **Initializes Database**: PostgreSQL (production) or SQLite (dev)
- **Sets up Redis** for session caching, JWT blocklist
- **Configures Mail Service** (SMTP/SES/Resend)
- **Health Check Endpoints**: `/healthz`, `/ready`
---
4. Database Setup and Models
Database Backends
The project supports two database backends:
1. SQLite (app/database.py) - Development:
   - Uses WAL mode for concurrency
   - Connection pooling via SQLAlchemy QueuePool
2. PostgreSQL (app/database_pg.py) - Production:
   - Uses psycopg2 with RealDictCursor
   - Connection pooling
Core Database Tables
Table	Purpose
users	User accounts with credentials, MFA secrets, roles
sessions	Active user sessions with IP/UA binding, assurance levels
behavioral_data	Encrypted keystroke/mouse features (Fernet encryption)
auth_events	Authentication event logging
model_metadata	Per-user ML model metadata (version, accuracy, drift)
audit_evidence	Tamper-evident audit chain (hash-linked for RBI compliance)
password_reset_tokens	Secure password reset token storage
consent_records	DPDP Act 2023 consent management
otp_codes	Real-time OTP storage with expiration
beneficiaries	Banking beneficiaries
cards	Payment cards with CVV hashing
investments	Investment holdings
notifications	User notifications
Key Database Features
- Fernet Encryption: Behavioral features encrypted at rest
- Audit Chain: SHA-256 hash chain for tamper evidence (RBI 7-year retention)
- DPDP Compliance: Data minimization, consent management, right-to-erasure
- Indexes: Optimized for common queries (user_id, timestamp, session)
Database Access Pattern
from app.extensions import get_db
db = get_db()
user = db.get_user_by_username("john")
---
5. API Architecture (Flask-RESTX)
Registered Namespaces (14 total)
Namespace	Path	Purpose
auth_ns	/api/v1/auth	Registration, login, logout, MFA, password reset
session_ns	/api/v1/session	Session management, context binding
behavioral_ns	/api/v1/behavioral	Behavioral data submission, scoring
transaction_ns	/api/v1/transaction	Transaction signing, risk assessment
admin_ns	/api/v1/admin	Admin operations, user management
compliance_ns	/api/v1/compliance	Audit retrieval, DSAR, consent
banking_ns	/api/v1/banking	Account balances, transfers
health_ns	/api/v1/health	Health check endpoints
webhooks_ns	/api/v1/webhooks	External system callbacks
user_ns	/api/v1/user	User profile operations
notifications_ns	/api/v1/notifications	Notification management
beneficiaries_ns	/api/v1/beneficiaries	Beneficiary CRUD
investments_ns	/api/v1/investments	Investment portfolio
cards_ns	/api/v1/cards	Card management
All responses follow standardized envelope: {"data": {...}} or {"error": {...}}
---
6. Machine Learning Architecture
ML Ensemble (app/ml_ensemble.py)
The system uses a 9-engine ensemble for risk scoring:
Engine	Purpose
CognitiveEngine	Intent detection (APP fraud, duress, bot, takeover)
DuressDetector	43-feature stress/coercion detection
LivenessDetector	Bot vs human verification
InvisibleChallengeEngine	Silent challenge responses (Patent US20150205955A1)
DeviceIntelligence	RAT, emulator, geo-velocity detection
CompositeSignalEngine	Lie detection, multi-user patterns
PassiveEnrollmentManager	BioCatch-style silent profile building
PerUserFeatureSelector	Top-20 unique features per user
TransactionHistoryBaseline	Amount/beneficiary/timing anomalies
Feature Extraction
Two-tier feature extraction:
1. feature_extractor.py - Core 38 features:
   - 18 keystroke features (hold time, flight time, typing speed, rhythm)
   - 20 mouse features (velocity, acceleration, curvature, clicks)
2. behavioral_feature_engine.py - Extended 200+ features across 8 categories:
   - Mouse & Pointer Dynamics (40+)
   - Keystroke Dynamics (35+)
   - Cognitive/Behavioral Signals (25+)
   - Duress & Social Engineering (15+)
   - Invisible Challenge Responses (12+)
   - Physiological Signals (18+)
   - Device & Contextual Signals (20+)
   - Derived & Composite Signals (30+)
---
7. Banking Integration (app/banking/)
Module	Purpose
cbs_adapters.py	Core Banking System mocks (Finacle/BaNCS)
npci_risk.py	NPCI risk network simulation
app_fraud.py	Authorized Push Payment (APP) fraud detection
---
## 8. Supporting Infrastructure
### Extensions (`app/extensions.py`)
- `limiter` - Rate limiting
- `get_db()` - Database accessor
- `get_redis()` - Redis accessor
### Key Modules
- **`app/redis_store.py`** - Redis client management
- **`app/mail.py`** - Email service (SMTP/SES/Resend)
- **`app/tasks.py`** - Celery async task queue
- **`app/alerts.py`** - Alert management
- **`app/metrics.py`** - Prometheus metrics
- **`app/drift_detector.py`** - ADWIN statistical drift detection
- **`app/extended_risk_scorer.py`** - BioCatch-style risk scoring
- **`app/error_handling.py`** - Structured error responses
- **`app/logging_config.py`** - Structured logging setup
---
9. Testing Infrastructure (tests/)
Test File	Coverage
test_comprehensive.py	Full system integration
test_mfa.py	Multi-factor authentication
test_security_audit.py	Security vulnerabilities
test_ml_models.py	ML model accuracy
test_admin_compliance.py	RBI/DPDP compliance
test_banking_intelligence.py	Banking features
locustfile.py	Load/performance testing
---
## 10. Production Deployment
### Docker Compose Services
- **web**: Flask application (port 5000)
- **redis**: Rate limiting & caching (port 6379)
- **db**: PostgreSQL 15 (port 5432)
- **celery_worker**: Async task processing
### Kubernetes (Helm)
- Deployment, HPA, PDB, ConfigMap, Secrets in `helm/behavior-auth/`
---
This is a world-class, enterprise-grade continuous authentication system that mimics industry leaders like BioCatch. It provides dual-layer intelligence (physical biometrics + cognitive intent detection) while maintaining GDPR/DPDP compliance through passive, privacy-preserving behavioral analysis.
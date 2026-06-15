<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/Flask-3.x-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" />
  <img src="https://img.shields.io/badge/Next.js-16-000000?style=for-the-badge&logo=next.js&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black" alt="React" />
  <img src="https://img.shields.io/badge/TailwindCSS-4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white" alt="TailwindCSS" />
  <img src="https://img.shields.io/badge/scikit--learn-1.3+-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white" alt="scikit-learn" />
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Coverage-80%25+-brightgreen?style=flat-square" alt="Coverage" />
  <img src="https://img.shields.io/badge/ML_Engines-13-blueviolet?style=flat-square" alt="ML Engines" />
  <img src="https://img.shields.io/badge/Tests-18_suites-blue?style=flat-square" alt="Tests" />
  <img src="https://img.shields.io/badge/API_Namespaces-14-orange?style=flat-square" alt="API" />
  <img src="https://img.shields.io/badge/DPDP_Act-Compliant-success?style=flat-square" alt="DPDP" />
  <img src="https://img.shields.io/badge/PCI_DSS-4.0-success?style=flat-square" alt="PCI DSS" />
</p>

# 🛡️ AetherAuth — Behavioral Biometrics Authentication

> **Enterprise-grade continuous authentication system** that uses keystroke dynamics, mouse movement analysis, and cognitive behavioral patterns to invisibly verify user identity — no CAPTCHAs, no friction.

Built to meet **RBI Master Directions 2021**, **PCI DSS 4.0**, and **DPDP Act 2023** compliance requirements for banking and enterprise security.

---

## 📑 Table of Contents

- [Features](#-features)
- [Architecture Overview](#-architecture-overview)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Environment Variables](#-environment-variables)
- [API Reference](#-api-reference-14-namespaces)
- [Machine Learning Pipeline](#-machine-learning-pipeline)
- [Database Schema](#-database-schema)
- [Frontend Architecture](#-frontend-architecture)
- [Banking Integration](#-banking-integration)
- [Security & Compliance](#-security--compliance)
- [Testing](#-testing)
- [Deployment](#-deployment)
  - [Vercel (Frontend)](#vercel-frontend)
  - [Render (Backend)](#render-backend)
  - [Docker Compose](#docker-compose)
  - [Kubernetes (Helm)](#kubernetes-helm)
- [CI/CD Pipeline](#-cicd-pipeline)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### Core Authentication
- 🔐 **Continuous behavioral authentication** — verify users by *how* they type & move, not just passwords
- 🧠 **9-engine ML ensemble** — Cognitive Engine, Duress Detector, Liveness Detector, Invisible Challenges, Device Intelligence, Composite Signals, Passive Enrollment, Per-User Feature Selection, Transaction Baseline
- ⌨️ **200+ behavioral features** — keystroke hold/flight time, typing rhythm, mouse velocity, curvature, acceleration, scroll patterns, and cognitive signals
- 🔄 **Passive enrollment** — BioCatch-style silent profile building without user interaction
- 🛑 **Duress detection** — 43-feature stress/coercion analysis to detect socially-engineered sessions

### Security
- 🔑 **Multi-factor authentication** — TOTP, OTP via email, backup codes
- 🛡️ **Step-up authentication** — risk-based MFA challenges only when anomalies are detected
- 🔒 **Fernet encryption at rest** — all behavioral data encrypted with rotating keys
- 📝 **Tamper-evident audit chain** — SHA-256 hash-linked audit logs (RBI 7-year retention)
- 🚫 **Bot & RAT detection** — automated tool, emulator, and remote access detection
- 🌐 **Geo-velocity anomaly detection** — impossible travel detection
- ✍️ **Transaction signing** — HMAC-based transaction integrity verification

### Frontend
- 🎨 **Premium dark UI** — glassmorphism, animations, responsive design with Framer Motion
- 📊 **Real-time dashboards** — trust score timeline, risk gauges, keystroke heatmaps
- 🔔 **Live behavioral overlay** — real-time biometric confidence visualization
- 📱 **Mobile-responsive** — works on desktop, tablet, and mobile
- ⚡ **Vercel Speed Insights** — performance monitoring built-in

### Compliance
- 🏦 **RBI Master Directions 2021** — full compliance with Indian banking regulations
- 💳 **PCI DSS 4.0** — payment card industry security standards
- 📋 **DPDP Act 2023** — data privacy, consent management, right-to-erasure
- 🔍 **DSAR support** — automated Data Subject Access Request handling
- 📊 **Explainability** — human-readable risk explanations for every decision

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Next.js 16)                       │
│   Landing Page │ Login │ Signup │ Dashboard │ Admin │ Compliance     │
│   ┌──────────────────────────────────────────────────┐              │
│   │  BehavioralCollector (69KB) - 200+ Features      │              │
│   │  Keystroke/Mouse/Touch/Scroll/Cognitive Capture   │              │
│   └──────────────────────────────────────────────────┘              │
│                              ↓ (via API routes / rewrites)          │
├─────────────────────────────────────────────────────────────────────┤
│                      BACKEND (Flask + Flask-RESTX)                  │
│   14 API Namespaces │ JWT + CSRF │ Rate Limiting │ CORS             │
│   ┌──────────────────────────────────────────────────┐              │
│   │  ML Ensemble Pipeline                            │              │
│   │  ┌─────────┐ ┌─────────┐ ┌──────────────────┐   │              │
│   │  │Cognitive│ │Duress   │ │Liveness          │   │              │
│   │  │Engine   │ │Detector │ │Detector          │   │              │
│   │  └─────────┘ └─────────┘ └──────────────────┘   │              │
│   │  ┌─────────┐ ┌─────────┐ ┌──────────────────┐   │              │
│   │  │Invisible│ │Device   │ │Composite Signal  │   │              │
│   │  │Challenge│ │Intel    │ │Engine            │   │              │
│   │  └─────────┘ └─────────┘ └──────────────────┘   │              │
│   │  ┌─────────────┐ ┌─────────┐ ┌──────────────┐   │              │
│   │  │Passive      │ │Per-User │ │Transaction   │   │              │
│   │  │Enrollment   │ │Feature  │ │Baseline      │   │              │
│   │  └─────────────┘ └─────────┘ └──────────────┘   │              │
│   └──────────────────────────────────────────────────┘              │
│                              ↓                                      │
├─────────────────────────────────────────────────────────────────────┤
│           DATA LAYER                                                │
│   SQLite (dev) │ PostgreSQL (prod) │ Redis (cache/sessions)         │
│   Fernet Encryption │ Alembic Migrations │ Audit Chain              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 16, React 19, TypeScript 5.9 | Server components, app router, SSR |
| **Styling** | TailwindCSS 4, Framer Motion | Animations, responsive dark UI |
| **Charts** | Recharts 3 | Trust timeline, risk gauges, sparklines |
| **Backend** | Flask 3.x, Flask-RESTX | REST API with Swagger/OpenAPI docs |
| **Auth** | Flask-JWT-Extended, PyOTP, bcrypt | JWT, TOTP MFA, secure password hashing |
| **ML/AI** | scikit-learn, NumPy, SciPy, Pandas | Behavioral model training & inference |
| **Database** | SQLite (dev), PostgreSQL 15 (prod) | Persistent data with SQLAlchemy |
| **Cache** | Redis 7 | Sessions, rate limiting, JWT blocklist |
| **Queue** | Celery 5.4 | Async task processing |
| **Email** | SMTP / AWS SES / Resend | Password reset, OTP delivery |
| **Security** | cryptography (Fernet), HMAC | Encryption at rest, transaction signing |
| **DevOps** | Docker, Kubernetes (Helm), GitHub Actions | CI/CD, containerization, orchestration |

---

## 📂 Project Structure

```
behavioral-biometrics/
├── app/                          # 🐍 Flask Backend
│   ├── api/                      # API Endpoints (14 namespaces)
│   │   ├── auth.py               #   Registration, login, logout, MFA, password reset
│   │   ├── session.py            #   Session management, context binding
│   │   ├── behavioral.py         #   Behavioral data submission & scoring
│   │   ├── transaction.py        #   Transaction signing & risk assessment
│   │   ├── admin.py              #   Admin operations, user management
│   │   ├── compliance.py         #   Audit retrieval, DSAR, consent
│   │   ├── banking.py            #   Account balances, transfers
│   │   ├── health.py             #   Health check endpoints
│   │   ├── webhooks.py           #   External system callbacks
│   │   ├── user.py               #   User profile operations
│   │   ├── notifications.py      #   Notification management
│   │   ├── beneficiaries.py      #   Beneficiary CRUD
│   │   ├── investments.py        #   Investment portfolio
│   │   ├── cards.py              #   Card management
│   │   ├── ml_status.py          #   ML model status & metrics
│   │   └── helpers.py            #   Shared API utilities
│   ├── models/                   # ML Model Implementations
│   │   ├── ml_models.py          #   Core ML model (71KB - Isolation Forest, SVM, etc.)
│   │   ├── cognitive_engine.py   #   Intent detection (fraud, duress, bot, takeover)
│   │   ├── duress_detector.py    #   43-feature stress/coercion detection
│   │   ├── liveness_detector.py  #   Bot vs human verification
│   │   ├── invisible_challenge_engine.py  # Silent challenge responses
│   │   ├── device_intelligence.py         # RAT, emulator, geo-velocity
│   │   ├── composite_signal_engine.py     # Multi-signal fusion
│   │   ├── passive_enrollment.py          # BioCatch-style profile building
│   │   ├── per_user_feature_selector.py   # Top-20 features per user
│   │   ├── transaction_baseline.py        # Transaction anomaly detection
│   │   ├── ensemble.py           #   Ensemble orchestrator
│   │   ├── bayesian_fusion.py    #   Bayesian score fusion
│   │   ├── anomaly_detectors.py  #   Anomaly detection algorithms
│   │   ├── digraph_profile.py    #   Keystroke digraph profiling
│   │   ├── adwin_drift.py        #   ADWIN statistical drift detection
│   │   ├── sequence_models.py    #   Sequence-based models
│   │   ├── transformer_model.py  #   Transformer architecture
│   │   ├── siamese_network.py    #   Siamese network for verification
│   │   ├── simclr.py             #   SimCLR contrastive learning
│   │   ├── gan_adversarial.py    #   GAN adversarial detection
│   │   └── incremental_classifiers.py  # Online learning classifiers
│   ├── banking/                  # Banking Integration
│   │   ├── cbs_adapters.py       #   Core Banking System mocks (Finacle/BaNCS)
│   │   ├── npci_risk.py          #   NPCI risk network simulation
│   │   └── app_fraud.py          #   Authorized Push Payment fraud detection
│   ├── compliance/               # Regulatory Compliance Module
│   ├── services/                 # Business Logic Layer
│   │   ├── auth_service.py       #   Authentication service
│   │   ├── behavioral_enrollment.py  # Enrollment workflows
│   │   ├── cbs_service.py        #   CBS integration service
│   │   ├── transaction_service.py    # Transaction processing
│   │   └── synthetic_data.py     #   Synthetic data generation
│   ├── schemas/                  # Pydantic Validation Schemas
│   ├── repositories/             # Data Access Layer (Repository Pattern)
│   │   ├── user_repository.py       # User CRUD, authentication
│   │   ├── session_repository.py    # Session lifecycle
│   │   ├── audit_repository.py      # Compliance audit evidence
│   │   ├── behavioral_repository.py # Keystroke/mouse data, snapshots, risk timeline
│   │   ├── banking_repository.py    # Beneficiaries, cards, investments, notifications
│   │   └── enrollment_repository.py # Enrollment state, digraph profiles, devices
│   ├── performance/              # Performance monitoring
│   ├── config.py                 # Pydantic-based settings (270+ config values)
│   ├── app_impl.py               # Application factory (create_app)
│   ├── database.py               # Database operations (103KB)
│   ├── ml_ensemble.py            # ML ensemble orchestrator
│   ├── feature_extractor.py      # Core 38 features extraction
│   ├── behavioral_feature_engine.py  # Extended 200+ features
│   ├── drift_detector.py         # ADWIN drift detection
│   ├── extended_risk_scorer.py   # BioCatch-style risk scoring
│   ├── mail.py                   # Email service (SMTP/SES/Resend)
│   ├── redis_store.py            # Redis client management
│   ├── tasks.py                  # Celery async tasks
│   ├── validators.py             # Input validation (21KB)
│   ├── webhooks.py               # Webhook delivery
│   ├── metrics.py                # Prometheus metrics
│   ├── alerts.py                 # Alert management
│   └── error_handling.py         # Structured error responses
├── frontend/                     # ⚛️ Next.js Frontend
│   ├── src/
│   │   ├── app/                  # App Router Pages
│   │   │   ├── page.tsx          #   Landing page
│   │   │   ├── login/            #   Login with behavioral collection
│   │   │   ├── signup/           #   Registration
│   │   │   ├── dashboard/        #   Banking dashboard
│   │   │   │   ├── page.tsx      #     Main dashboard
│   │   │   │   ├── transfers/    #     Fund transfers
│   │   │   │   ├── investments/  #     Investment portfolio
│   │   │   │   ├── calibration/  #     Behavioral calibration
│   │   │   │   └── explainability/ #   ML explainability view
│   │   │   ├── admin/            #   Admin panel
│   │   │   ├── otp/              #   OTP verification
│   │   │   ├── account-recovery/ #   Account recovery flow
│   │   │   ├── forgot-password/  #   Password reset
│   │   │   ├── reset-password/   #   Password reset confirmation
│   │   │   ├── verify-email/     #   Email verification
│   │   │   ├── compliance/       #   Compliance dashboard
│   │   │   ├── architecture/     #   System architecture viewer
│   │   │   ├── demo/             #   Interactive demo
│   │   │   ├── privacy/          #   Privacy policy
│   │   │   └── challenge/        #   Step-up challenge
│   │   ├── components/           # Reusable Components
│   │   │   ├── behavioral/       #   Behavioral UI
│   │   │   │   ├── BehavioralIntelligenceOverlay.tsx  # Real-time biometric overlay
│   │   │   │   ├── BiometricScanner.tsx               # Scanner animation
│   │   │   │   ├── DataQualityRadar.tsx               # Data quality visualization
│   │   │   │   ├── GlobalPasteWarning.tsx             # Paste detection warning
│   │   │   │   ├── KeystrokeHeatmap.tsx               # Per-key heatmap
│   │   │   │   └── TypingDNA.tsx                      # TypingDNA-style UI
│   │   │   ├── charts/           #   Chart components
│   │   │   │   ├── RiskGauge.tsx  #    Risk score gauge
│   │   │   │   ├── TrustTimelineChart.tsx  # Trust score timeline
│   │   │   │   └── Sparkline.tsx  #    Mini sparkline charts
│   │   │   ├── auth/             #   Auth UI primitives
│   │   │   ├── NavBar.tsx        #   Navigation bar
│   │   │   ├── Footer.tsx        #   Footer
│   │   │   ├── BehavioralProvider.tsx       # Behavioral context provider
│   │   │   ├── SessionTimeoutWarning.tsx    # Session timeout modal
│   │   │   ├── TelemetryProvider.tsx        # Telemetry context
│   │   │   ├── NotificationBell.tsx         # Notification dropdown
│   │   │   └── ErrorBoundary.tsx            # Error boundary
│   │   ├── hooks/                # Custom React Hooks
│   │   │   └── useAutoPageContext.ts  # Auto page context detection
│   │   ├── lib/                  # Shared Utilities
│   │   │   ├── behavioral-collector.ts  # 200+ feature collector (69KB)
│   │   │   ├── api-client.ts     #   API client with CSRF & JWT refresh
│   │   │   ├── auth-utils.ts     #   Auth helper functions
│   │   │   ├── backend-url.ts    #   Backend URL resolver
│   │   │   ├── calibration.ts    #   Calibration utilities
│   │   │   ├── otp.ts            #   OTP utilities
│   │   │   └── utils.ts          #   General utilities
│   │   └── middleware.ts         # Next.js middleware (auth guards)
│   ├── next.config.mjs           # Next.js config (CSP, rewrites, headers)
│   ├── tailwind.config.ts        # TailwindCSS 4 configuration
│   └── package.json              # Frontend dependencies
├── tests/                        # 🧪 Test Suite (18 test files)
│   ├── conftest.py               #   Pytest fixtures & app factory
│   ├── test_comprehensive.py     #   Full system integration (36KB)
│   ├── test_blueprints.py        #   API blueprint tests
│   ├── test_coverage_boost.py    #   Coverage enhancement tests
│   ├── test_mfa.py               #   Multi-factor authentication
│   ├── test_security_audit.py    #   Security vulnerability tests
│   ├── test_ml_models.py         #   ML model accuracy tests
│   ├── test_admin_compliance.py  #   RBI/DPDP compliance tests
│   ├── test_banking_intelligence.py  # Banking feature tests
│   ├── test_production_features.py   # Production feature tests
│   ├── test_netbanking_fixes.py  #   Netbanking regression tests
│   ├── test_invisible_challenges.py  # Invisible challenge tests
│   ├── test_repositories.py      #   Repository pattern tests (17 tests)
│   ├── test_validators.py        #   Input validation tests (38 tests)
│   ├── test_error_handling.py    #   Error classes & context tests (20 tests)
│   ├── test_config_validation.py #   Settings/config tests (7 tests)
│   ├── test_mail_service.py      #   Mail service tests (12 tests)
│   └── locustfile.py             #   Load/performance testing (Locust)
├── alembic/                      # Database migrations
├── docs/                         # Documentation
│   ├── ARCHITECTURE.md           #   Architecture deep-dive
│   ├── DEPLOYMENT_RUNBOOK.md     #   Deployment procedures
│   ├── MODEL_CARD.md             #   ML model card
│   └── security/                 #   Security documentation
│       ├── control-mapping.md    #     Security control mapping
│       ├── incident-response-runbook.md  # Incident response
│       └── key-rotation-sop.md   #     Key rotation procedures
├── helm/                         # Kubernetes Helm charts
│   └── behavior-auth/            #   Deployment, HPA, PDB, ConfigMap, Secrets
├── .github/workflows/ci.yml      # GitHub Actions CI/CD
├── Dockerfile                    # Multi-stage production build
├── docker-compose.yml            # Full-stack local setup
├── render.yaml                   # Render deployment config
├── vercel.json                   # Vercel deployment config
├── Procfile                      # Heroku/Render process file
├── requirements.txt              # Python dependencies
├── requirements-dev.txt          # Dev dependencies
├── requirements-ml.txt           # ML extra dependencies
├── pyproject.toml                # Python project config & tooling
├── .env.example                  # Environment variable template
└── train_models.py               # ML model training script
```

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.10+
- **Node.js** 20+
- **Redis** 7+ (optional for dev, required for production)
- **PostgreSQL** 15+ (optional, SQLite used in dev)

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/harctik/behavioral-biometrics.git
cd behavioral-biometrics

# Create and activate virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# For development tools (pytest, ruff, black, etc.)
pip install -r requirements-dev.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your values (especially SECRET_KEY and JWT_SECRET_KEY)

# Run database migrations
alembic upgrade head

# Start the backend server
python run.py
# Backend runs at http://localhost:5000
# Swagger API docs at http://localhost:5000/api/v1/
```

### Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Create local environment
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL=http://127.0.0.1:5000

# Start development server
npm run dev
# Frontend runs at http://localhost:3000
```

---

## 🔐 Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | ✅ | Flask secret key (32+ random bytes) |
| `JWT_SECRET_KEY` | ✅ | JWT signing key (32+ random bytes) |
| `BACKUP_FERNET` | ✅ | Fernet key for backup code encryption |
| `DATABASE_PATH` | ❌ | SQLite path (default: `database/auth_system.db`) |
| `REDIS_URL` | ⚠️ prod | Redis connection string |
| `CORS_ORIGINS` | ⚠️ prod | Allowed frontend origins (comma-separated) |
| `MAIL_SERVER` | ❌ | SMTP server for email delivery |
| `MAIL_USERNAME` | ❌ | SMTP username |
| `MAIL_PASSWORD` | ❌ | SMTP password |
| `TXN_SIGNING_KEY` | ✅ | Transaction HMAC signing key |
| `RATELIMIT_STORAGE_URI` | ⚠️ prod | Redis URI for rate limiting |
| `FLASK_ENV` | ❌ | `development` / `production` / `testing` |
| `RISK_HIGH_THRESHOLD` | ❌ | High risk threshold (default: 0.65) |
| `RISK_MEDIUM_THRESHOLD` | ❌ | Medium risk threshold (default: 0.35) |

Frontend variables (in `frontend/.env.local`):

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | ✅ | Backend API URL |
| `BACKEND_URL` | ❌ | Server-side backend URL (overrides NEXT_PUBLIC_API_URL) |
| `JWT_SECRET_KEY` | ✅ | Must match backend JWT_SECRET_KEY |

> See [`.env.example`](.env.example) for the full list with detailed comments.

---

## 📡 API Reference (14 Namespaces)

All endpoints are prefixed with `/api/v1/` and documented via Swagger at `/api/v1/`.

| Namespace | Path | Description |
|-----------|------|-------------|
| **Auth** | `/api/v1/auth/*` | Registration, login, logout, MFA setup, password reset, token refresh |
| **Session** | `/api/v1/session/*` | Session creation, validation, context binding, assurance levels |
| **Behavioral** | `/api/v1/behavioral/*` | Behavioral data submission, risk scoring, model status |
| **Transaction** | `/api/v1/transaction/*` | Transaction signing, risk assessment, fraud detection |
| **Admin** | `/api/v1/admin/*` | User management, system stats, model retraining triggers |
| **Compliance** | `/api/v1/compliance/*` | Audit log retrieval, DSAR requests, consent management |
| **Banking** | `/api/v1/banking/*` | Account balances, fund transfers, statement generation |
| **Health** | `/api/v1/health/*` | Liveness (`/healthz`) and readiness (`/ready`) probes |
| **Webhooks** | `/api/v1/webhooks/*` | External system callbacks |
| **User** | `/api/v1/user/*` | Profile view/update, settings management |
| **Notifications** | `/api/v1/notifications/*` | Notification listing, read status, preferences |
| **Beneficiaries** | `/api/v1/beneficiaries/*` | Beneficiary CRUD operations |
| **Investments** | `/api/v1/investments/*` | Investment portfolio management |
| **Cards** | `/api/v1/cards/*` | Card listing, activation, limits |

### Response Format

All responses follow a standardized envelope:

```json
// Success
{ "data": { ... } }

// Error
{ "error": { "message": "...", "code": "..." } }
```

### Key Authentication Flows

```
Register → Login → MFA Setup → Behavioral Enrollment
                       ↓
              Session Created (JWT + CSRF)
                       ↓
           Continuous Behavioral Scoring
                       ↓
         Risk Score > Threshold? → Step-up MFA
```

---

## 🤖 Machine Learning Pipeline

### 9-Engine Ensemble

| Engine | Module | Purpose |
|--------|--------|---------|
| **CognitiveEngine** | `cognitive_engine.py` | Intent detection (APP fraud, duress, bot, account takeover) |
| **DuressDetector** | `duress_detector.py` | 43-feature stress/coercion detection |
| **LivenessDetector** | `liveness_detector.py` | Bot vs human verification |
| **InvisibleChallengeEngine** | `invisible_challenge_engine.py` | Silent challenge-response (Patent US20150205955A1) |
| **DeviceIntelligence** | `device_intelligence.py` | RAT, emulator, geo-velocity detection |
| **CompositeSignalEngine** | `composite_signal_engine.py` | Multi-signal lie detection, multi-user patterns |
| **PassiveEnrollmentManager** | `passive_enrollment.py` | BioCatch-style silent profile building (40KB) |
| **PerUserFeatureSelector** | `per_user_feature_selector.py` | Top-20 unique discriminative features per user |
| **TransactionHistoryBaseline** | `transaction_baseline.py` | Amount/beneficiary/timing anomaly detection |

### Feature Extraction (Two-Tier)

**Tier 1 — Core 38 Features** (`feature_extractor.py`):
- 18 keystroke features: hold time, flight time, typing speed, rhythm, pressure
- 20 mouse features: velocity, acceleration, curvature, click patterns

**Tier 2 — Extended 200+ Features** (`behavioral_feature_engine.py`):
| Category | Count | Examples |
|----------|-------|---------|
| Mouse & Pointer Dynamics | 40+ | Velocity histogram, Bézier curvature, micro-tremor |
| Keystroke Dynamics | 35+ | Digraph timing, n-gram rhythm, error correction rate |
| Cognitive/Behavioral Signals | 25+ | Hesitation patterns, decision latency, scan path |
| Duress & Social Engineering | 15+ | Typing under stress, unusual pause patterns |
| Invisible Challenge Responses | 12+ | Silent challenge timing, response consistency |
| Physiological Signals | 18+ | Circadian rhythm, fatigue detection |
| Device & Contextual Signals | 20+ | Screen resolution, timezone, accelerometer |
| Derived & Composite Signals | 30+ | Cross-feature correlations, temporal patterns |

### Advanced ML Models

| Model | File | Architecture |
|-------|------|-------------|
| Isolation Forest + SVM | `ml_models.py` | Anomaly detection ensemble |
| Bayesian Fusion | `bayesian_fusion.py` | Probabilistic score fusion |
| ADWIN Drift Detection | `adwin_drift.py` | Adaptive windowing for concept drift |
| Digraph Profile | `digraph_profile.py` | Per-key-pair timing models |
| Transformer | `transformer_model.py` | Sequential behavior modeling |
| Siamese Network | `siamese_network.py` | One-shot verification |
| SimCLR | `simclr.py` | Contrastive self-supervised learning |
| GAN Adversarial | `gan_adversarial.py` | Adversarial attack detection |
| Incremental Classifiers | `incremental_classifiers.py` | Online learning adaptation |

### Training

```bash
# Train models for all users with sufficient data
python train_models.py

# Models are saved to models/saved/<user_id>/
```

---

## 💾 Database Schema

### Core Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts with credentials, MFA secrets, roles |
| `sessions` | Active sessions with IP/UA binding, assurance levels |
| `behavioral_data` | Encrypted keystroke/mouse features (Fernet encryption) |
| `auth_events` | Authentication event logging |
| `model_metadata` | Per-user ML model metadata (version, accuracy, drift) |
| `audit_evidence` | Tamper-evident audit chain (SHA-256 hash-linked) |
| `password_reset_tokens` | Secure password reset token storage |
| `consent_records` | DPDP Act 2023 consent management |
| `otp_codes` | Real-time OTP storage with expiration |
| `beneficiaries` | Banking beneficiaries |
| `cards` | Payment cards with CVV hashing |
| `investments` | Investment holdings |
| `notifications` | User notifications |

### Key Data Features

- **Fernet Encryption**: All behavioral features encrypted at rest
- **Audit Chain**: SHA-256 hash chain for tamper evidence (RBI 7-year retention)
- **DPDP Compliance**: Data minimization, consent management, right-to-erasure
- **Optimized Indexes**: user_id, timestamp, session for high-performance queries

### Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 🎨 Frontend Architecture

### Pages (17 routes)

| Route | Component | Purpose |
|-------|-----------|---------|
| `/` | Landing Page | Marketing page with live behavioral demo |
| `/login` | Login | Email/password + behavioral collection |
| `/signup` | Signup | Registration with behavioral enrollment |
| `/otp` | OTP | One-time password verification |
| `/dashboard` | Dashboard | Banking dashboard with trust scores |
| `/dashboard/transfers` | Transfers | Fund transfer with risk-based approval |
| `/dashboard/investments` | Investments | Investment portfolio management |
| `/dashboard/calibration` | Calibration | Behavioral profile calibration |
| `/dashboard/explainability` | Explainability | ML decision explanations |
| `/admin` | Admin | User management, system stats |
| `/compliance` | Compliance | Audit logs, DSAR management |
| `/account-recovery` | Recovery | Account recovery flow |
| `/forgot-password` | Forgot Password | Password reset request |
| `/reset-password` | Reset Password | Password reset confirmation |
| `/verify-email` | Email Verification | Email confirmation |
| `/demo` | Demo | Interactive behavioral demo |
| `/privacy` | Privacy | Privacy policy |

### Key Components

- **`BehavioralCollector`** (69KB) — Captures 200+ behavioral features from keyboard, mouse, touch, scroll, and device sensors
- **`BehavioralIntelligenceOverlay`** — Real-time overlay showing biometric confidence scores
- **`KeystrokeHeatmap`** — Per-key visualization of typing patterns
- **`RiskGauge`** — Animated risk score gauge
- **`TrustTimelineChart`** — Historical trust score timeline with Recharts
- **`SessionTimeoutWarning`** — Countdown modal for session expiry
- **`NotificationBell`** — Real-time notification dropdown

### API Client

The frontend uses a central API client (`lib/api-client.ts`) with:
- Automatic CSRF token injection from cookies
- Silent JWT refresh on 401 responses
- Retry-once pattern for seamless token renewal

---

## 🏦 Banking Integration

| Module | Purpose |
|--------|---------|
| `cbs_adapters.py` | Core Banking System mocks (Finacle/BaNCS style) |
| `npci_risk.py` | NPCI risk network simulation |
| `app_fraud.py` | Authorized Push Payment (APP) fraud detection |

Features:
- Account balance and statement retrieval
- Fund transfers with risk-based approval
- Beneficiary management
- Card management with CVV hashing
- Investment portfolio tracking
- Transaction signing with HMAC verification

---

## 🔒 Security & Compliance

### Authentication Security
- **bcrypt** password hashing with configurable work factor
- **JWT** access + refresh tokens with httpOnly cookies
- **CSRF** per-session tokens (signed with SECRET_KEY)
- **Rate limiting** with Redis-backed Flask-Limiter
- **IP allowlist/denylist** enforcement
- **HTTPS redirect** in production
- **Security headers**: HSTS, CSP, X-Frame-Options, X-Content-Type-Options

### Data Protection
- **Fernet encryption** for behavioral data at rest
- **Key rotation** support for JWT and Fernet keys
- **Data minimization** — only store necessary behavioral features
- **Right-to-erasure** — DPDP Act compliance
- **Consent management** — granular consent records

### Compliance Standards

| Standard | Coverage |
|----------|----------|
| **RBI Master Directions 2021** | Continuous authentication, audit chain, 7-year retention |
| **PCI DSS 4.0** | Secure data handling, access controls, monitoring |
| **DPDP Act 2023** | Consent management, data minimization, right-to-erasure |
| **GDPR** | Data portability, right-to-access, privacy by design |

---

## 🧪 Testing

### Backend Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific test files
pytest tests/test_comprehensive.py
pytest tests/test_security_audit.py
pytest tests/test_ml_models.py
pytest tests/test_mfa.py
pytest tests/test_banking_intelligence.py
pytest tests/test_admin_compliance.py
```

### Test Coverage

| Test File | Coverage Area |
|-----------|---------------|
| `test_comprehensive.py` | Full system integration (36KB) |
| `test_blueprints.py` | API blueprint routing |
| `test_coverage_boost.py` | Coverage enhancement |
| `test_mfa.py` | Multi-factor authentication |
| `test_security_audit.py` | Security vulnerabilities |
| `test_ml_models.py` | ML model accuracy |
| `test_admin_compliance.py` | RBI/DPDP compliance |
| `test_banking_intelligence.py` | Banking features |
| `test_production_features.py` | Production features |
| `test_netbanking_fixes.py` | Netbanking regressions |
| `test_invisible_challenges.py` | Invisible challenges |

### Load Testing

```bash
# Run Locust load tests
locust -f tests/locustfile.py --host=http://localhost:5000
```

### Frontend Tests

```bash
cd frontend

# Unit tests
npm test

# E2E tests (Playwright)
npx playwright test
```

---

## 🚢 Deployment

### Vercel (Frontend)

The frontend deploys to **Vercel** as a Next.js application.

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy (from project root)
vercel

# Set environment variables in Vercel Dashboard:
# NEXT_PUBLIC_API_URL = https://your-render-backend.onrender.com
# BACKEND_URL = https://your-render-backend.onrender.com
# JWT_SECRET_KEY = (must match backend)
```

Configuration is in [`vercel.json`](vercel.json):
```json
{
  "framework": "nextjs",
  "installCommand": "cd frontend && npm install --include=dev",
  "buildCommand": "cd frontend && npm run build",
  "outputDirectory": "frontend/.next"
}
```

### Render (Backend)

The backend deploys to **Render** as a Python web service.

1. Connect your GitHub repo at [render.com](https://render.com)
2. Render auto-detects `render.yaml` and creates services
3. Set the following environment variables manually:
   - `FRONTEND_URL` → your Vercel frontend URL
   - `CORS_ORIGINS` → your Vercel frontend URL

Configuration is in [`render.yaml`](render.yaml).

### Docker Compose

Full-stack local deployment:

```bash
# Start all services (Flask + PostgreSQL + Redis + Celery + Frontend)
docker-compose up -d

# Services:
# - web:            Flask backend     → http://localhost:5000
# - frontend:       Next.js frontend  → http://localhost:3000
# - db:             PostgreSQL 15     → localhost:5432
# - redis:          Redis 7           → localhost:6379
# - celery_worker:  Async tasks
```

### Kubernetes (Helm)

Production-grade Kubernetes deployment:

```bash
# Install with Helm
helm install behavior-auth ./helm/behavior-auth \
  --set image.tag=latest \
  --set secrets.jwtSecret=your-secret

# Includes:
# - Deployment with HPA (auto-scaling)
# - PodDisruptionBudget
# - ConfigMap + Secrets
# - Service + Ingress
```

---

## 🔄 CI/CD Pipeline

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push to `main`/`develop`:

| Job | Description |
|-----|-------------|
| **Lint** | Black formatting, Ruff linting, MyPy type checking |
| **Frontend Build** | npm ci, ESLint, Next.js build |
| **Test** | pytest with coverage reporting + Codecov upload |
| **Security** | Bandit scan, Safety check, pip-audit |
| **Docker** | Build and push Docker image to Docker Hub |

```
Push → Lint → Frontend Build → Test → Security → Docker Build
                                 ↓
                          Codecov Upload
```

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

```bash
# Setup pre-commit hooks
pre-commit install

# Format code
black .

# Lint
ruff check .

# Type check
mypy app --ignore-missing-imports

# Run tests
pytest --cov=app
```

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <b>Built with ❤️ for next-generation banking security</b><br/>
  <sub>AetherAuthSecure — Authentication That Understands You</sub>
</p>
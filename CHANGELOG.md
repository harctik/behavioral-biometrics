# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-06-16

### Architecture
- **Repository Pattern**: Decomposed 2,469-line `DatabaseManager` into 6 focused repositories
  - `UserRepository` — user CRUD and authentication queries
  - `SessionRepository` — session lifecycle management
  - `AuditRepository` — compliance audit evidence
  - `BehavioralRepository` — keystroke/mouse biometric data, risk timeline
  - `BankingRepository` — beneficiaries, cards, investments, notifications
  - `EnrollmentRepository` — enrollment state, digraph profiles, device fingerprints
- Progressive migration: repositories delegate to DatabaseManager (non-breaking)

### ML Pipeline
- 13-engine Bayesian belief-update ensemble (upgraded from 10-engine weighted average)
- BioCatch-style per-user feature selection (top-20 from 200+ features)
- ADWIN adaptive drift detection for concept drift monitoring
- GAN adversarial discriminator for synthetic replay detection
- Siamese/SimCLR contrastive learning for behavioral representation

### Testing
- **18 test files** with comprehensive coverage across all layers
- New test suites: `test_repositories`, `test_validators`, `test_error_handling`, `test_config_validation`, `test_mail_service`
- Coverage threshold raised from 60% → 80%
- 96 new test cases (repositories: 17, validators: 38, error handling: 20, config: 7, mail: 12)

### Security
- Created root `SECURITY.md` with responsible disclosure policy
- Fixed default rate limit from 5/min → 60/min (auth endpoints retain stricter limits)
- Added `.env.docker` to `.gitignore`
- Docker resource limits (memory + CPU) for all 5 services

### Frontend
- **Accessibility (a11y)**: `focus-visible` ring styles, skip-to-content link, `htmlFor` labels, ARIA labels on all form inputs, `role="main"`, `aria-live` announcer region
- `theme-color` meta tag for mobile browsers
- Login and signup pages fully WCAG 2.1 AA compliant for form labeling

### Documentation
- Rewrote `MODEL_CARD.md` — full 13-engine table, Bayesian fusion, feature pipeline, drift detection, per-user selection
- Updated `CONTRIBUTING.md` — repository pattern architecture guide, 80% coverage requirement
- Updated `README.md` — 6 new badges, expanded project structure with repository listing, expanded test suite listing
- `ml_ensemble.py` module docstring updated to list all 13 engines
- Added `CHANGELOG.md` (this file)

### DevOps
- Docker Compose resource limits: memory + CPU constraints for db, redis, web, celery_worker, frontend
- Coverage configuration refined: removed omit for now-tested modules

## [0.9.0] — 2026-06-15

### Added
- Initial public release
- Flask 3.x backend with 14 API namespaces
- Next.js 16 frontend with React 19
- Behavioral biometrics collector (keystroke dynamics + mouse movement)
- ML ensemble with weighted average fusion
- MFA (TOTP) with encrypted secret storage
- Email verification and password reset flows
- Banking simulation (beneficiaries, cards, investments)
- Docker Compose multi-service deployment
- Kubernetes Helm charts
- Vercel (frontend) + Render (backend) deployment support
- RBI Master Directions 2021 / PCI DSS 4.0 / DPDP Act 2023 compliance

# 🛡️ BioCatch-Replica: Continuous Behavioral Authentication System

![image](https://github.com/user-attachments/assets/6709bbef-fb3c-4af3-a342-2f2e499f282e)
![image](https://github.com/user-attachments/assets/2b875343-07fb-4883-b946-61284c4f14d8)

A world-class, enterprise-grade continuous authentication platform utilizing **Cognitive Behavioral Biometrics**. Built as a replica of industry-leading systems like BioCatch, this project shifts the cybersecurity paradigm from traditional static authentication to continuous, passive, and invisible verification. 

Instead of just analyzing *how* a user types (physical biometrics), this system utilizes a **Cognitive Behavioral Engine** to model *why* a user's behavior changes, detecting intent, stress, coaching, and automation in real-time without requiring PII or intrusive permissions.

---

## 🌟 1. Core Architecture: The Dual-Layer Intelligence

The system operates using two distinct, parallel intelligence layers to maximize security and minimize false positives.

### Layer A: The ML Authenticity Pipeline (Who is this?)
This layer continuously verifies if the person behind the screen matches the historical baseline of the account owner. It extracts 38 distinct physical features every few seconds:
- **Keystroke Dynamics**: Flight time (time between keys), hold time (duration of keypress), digraph/trigraph timing, speed variance, and rhythm consistency.
- **Mouse Dynamics**: Movement efficiency, trajectory curvature, velocity smoothness, click duration, and direction change variance.
- **Touch Dynamics**: Radius measurements (X/Y spread of the finger), estimated force/pressure, and swipe velocity.
- **Ensemble Fusion**: Utilizes a weighted vote from multiple models including GRU (for sequence patterns), Autoencoders (for reconstruction loss anomalies), and Isolation Forests (for outlier detection).

### Layer B: The Cognitive Engine (What are they doing?)
This layer detects generalized fraud topologies independently of the user's historical profile. It looks for psychological and cognitive tells.
- **APP Fraud (Authorized Push Payment)**: Detects victims being coached over the phone. Flags `copy-paste` of sensitive fields coupled with `scripted_navigation` and a lack of natural corrections.
- **Duress & Coercion**: Detects `prolonged_hesitation` before high-value actions, `scroll_anxiety` (scrolling up and down nervously), and erratic `tab_switching`.
- **Bot & Automation**: Identifies `superhuman_navigation` (moving between fields instantly), `perfect_entropy` (clicking the exact same sequence every time), and `constant_scroll_speed`.
- **Account Takeover**: Triggers on sudden, mid-session rhythm changes via Mahalanobis distance drift detection, indicating someone else just sat down at the keyboard.

---

## 🏗️ 2. System Components & Repository Structure

The architecture strictly separates a high-performance Python/Flask ML backend from a modern Next.js React frontend.

```text
Behavior-Based-Authentication/
├── app/                             # Python Flask Backend
│   ├── app_impl.py                  # API routes, middleware, CSRF, JWT
│   ├── config.py                    # Enterprise configuration management
│   ├── database.py                  # SQLite WAL concurrency + schema definition
│   ├── feature_extractor.py         # Extracts the core 38 physical ML features
│   ├── extended_risk_scorer.py      # BioCatch-style behavioral signal scoring
│   ├── drift_detector.py            # ADWIN-based statistical drift detection
│   │
│   ├── models/                      # Machine Learning Ensemble
│   │   ├── ml_models.py             # Base models (GRU, SVM, kNN, Isolation Forest)
│   │   └── cognitive_engine.py      # Rule-based and probabilistic intent detection
│   │
│   └── banking/                     # Enterprise Banking Integrations
│       ├── cbs_adapters.py          # Core Banking System mocks (Finacle/BaNCS)
│       └── npci_risk.py             # NPCI risk network simulation
│
└── frontend/                        # Next.js 16 App Router (Enterprise UI)
    ├── src/app/                     
    │   ├── challenge/               # Real-time BioCatch intelligence console
    │   ├── dashboard/               # Main banking dashboard with real-time metrics
    │   └── calibration/             # Passive baseline building UI
    │
    └── src/lib/
        └── behavioral-collector.ts  # The silent, 7-dimensional data harvester
```

---

## 🛡️ 3. Privacy & Compliance by Design

This system adheres to the strictest data protection regulations (GDPR, DPDP Act) by utilizing true **Passive Biometrics**:
- **Zero PII**: The system analyzes *how* data is entered, never *what* is entered. Passwords and account numbers are never logged.
- **Zero Friction**: The collector runs silently in the background. Users are never asked to re-authenticate unless high cognitive risk is detected.
- **Zero Permissions**: Relies entirely on standard DOM events (`keydown`, `mousemove`, `scroll`, `devicemotion`). It **never** requests Camera, Microphone, or GPS access, ensuring maximum user trust.
- **Data Anonymization**: Dedicated compliance endpoints exist for DSAR (Data Subject Access Requests) to anonymize or export user telemetry.

---

## 🚀 4. Installation & Quick Start

### Prerequisites
- **Python 3.10+** (For the ML Backend)
- **Node.js 18+** (For the Next.js Frontend)

### Step 1: Start the Backend (Flask & ML)
```bash
# Clone the repository
git clone <repo-url>
cd Behavior-Based-Authentication-main

# Create and activate a virtual environment
python -m venv venv
# On Windows: venv\Scripts\activate
# On macOS/Linux: source venv/bin/activate

# Install all backend dependencies
pip install -r requirements.txt

# Start the Flask server (runs on port 5000 by default)
python run.py
```

### Step 2: Start the Frontend (Next.js)
```bash
# Open a new terminal window and navigate to the frontend directory
cd frontend

# Install Node modules
npm install

# Start the Next.js development server
npm run dev
```
Navigate your browser to `http://localhost:3000` to access the application.

---

## 🎯 5. Testing the Cognitive Engine (Interactive Demo)

Once you have created an account and logged into the system, navigate to the `/challenge` console. You can actively simulate various fraud vectors to watch the Cognitive Engine flag your behavior in real-time.

### Scenario A: Simulate a Bot / Automation Script
1. Refresh the page to start a clean session window.
2. **Do not use the mouse.** Use the `Tab` key to instantly snap between the input fields.
3. Type an amount extremely fast (or use an auto-filler if you have one) with zero typos.
4. Hit `Enter` to evaluate immediately.
5. **Result**: The engine will flag `bot:superhuman_navigation` and `bot:zero_cognitive_signals`, pushing the Global Risk gauge into the red.

### Scenario B: Simulate APP Fraud (Social Engineering Victim)
*Context: A scammer is on the phone instructing the victim to transfer money.*
1. Open a separate notepad application and type `15000`. Copy it to your clipboard.
2. In the dashboard, click the transfer amount field and hit `Ctrl+V` (Paste).
3. Hover your mouse over the "Evaluate Context" button, but **do not click it** for 3-4 seconds (simulating the victim listening to instructions/hesitating).
4. **Result**: The engine detects the clipboard usage combined with hesitation and triggers `app_fraud:COACHED_PATTERN` alongside `prolonged_hesitation`. The transaction decision will be overridden to `STEP_UP_REQUIRED` or `BLOCKED`.

### Scenario C: Simulate Duress / Anxiety
*Context: A user is nervous, perhaps being physically coerced or unsure of the transaction.*
1. Scroll up and down the page rapidly multiple times.
2. Type an amount, backspace the entire thing, and type it again slowly.
3. Switch browser tabs 2-3 times before coming back to submit.
4. **Result**: The engine recognizes the erratic behavior, triggering `duress:anxious_rereading`, `high_correction_rate`, and `tab_switches`.

---

## ⚙️ 6. Enterprise Configuration & Scaling

### Database Engine
This project utilizes **SQLite configured with Write-Ahead Logging (WAL)**. WAL mode allows concurrent reads and writes, making it highly capable of handling the high-volume, rapid telemetry ingestion required by continuous authentication without the operational overhead of managing a dedicated PostgreSQL cluster during initial deployment.

### Secret Management
Create a `.env` file in the root directory:
```env
SECRET_KEY=your-flask-secret-key-super-secure
JWT_SECRET_KEY=your-jwt-signing-key
TRANSACTION_SIGNING_REQUIRED=True
TXN_SIGNING_KEY=your-transaction-signature-key
```

### ML Hyperparameters
Located in `app/config.py`, you can tune the strictness of the system:
```python
CONFIDENCE_THRESHOLD = 0.75          # Minimum authenticity score
ANOMALY_SCORE_THRESHOLD = 0.80       # When to trigger a step-up challenge
MIN_PASSIVE_SESSIONS = 5             # Sessions required to build a baseline
WINDOW_SIZE = 30                     # Telemetry aggregation window (seconds)
```

---

## 🔮 7. Future Roadmap

1. **Federated Learning Support**: Allowing mobile devices to train their specific behavioral models locally, sending only encrypted weight updates to the server to maximize privacy.
2. **Context-Aware Authentication**: Fusing behavioral data with environmental data (Time of day, typical IP subnets, BSSID geofencing).
3. **Graph-Based Threat Intel**: Linking behavioral signatures across multiple accounts to detect organized fraud rings utilizing similar automated scripts.

---
*Developed as an advanced exploration into cognitive security and behavioral biometrics.*

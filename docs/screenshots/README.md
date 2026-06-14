# Screenshots Guide

This directory is reserved for screenshots of the BehaviorGuard user interface and dashboards.

## How to capture screenshots:

1. **Start the application stack**:
   ```bash
   docker compose up -d --build
   ```
2. **Access the Frontend**:
   Navigate to [http://localhost:3000](http://localhost:3000).
3. **Capture key screens**:
   - **Login Page**: Show the secure login interface.
   - **MFA Step**: Show the TOTP verification screen.
   - **Dashboard**: Show the real-time trust score timeline and anomaly detection statistics.
   - **Risk Events**: Show the security analyst view of risk alerts.
4. **Save screenshots** in this directory as PNG files (e.g., `login.png`, `mfa.png`, `dashboard.png`) to be referenced in the main documentation.

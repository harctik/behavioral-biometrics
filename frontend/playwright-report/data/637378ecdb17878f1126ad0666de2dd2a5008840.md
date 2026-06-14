# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: behavioral.spec.ts >> Behavioral Authentication Flow >> Bot-like login is detected and rejected or challenged
- Location: tests\behavioral.spec.ts:4:7

# Error details

```
Error: expect(page).toHaveURL(expected) failed

Expected pattern: /.*\/challenge|\/otp/
Received string:  "http://localhost:3000/login"
Timeout: 5000ms

Call log:
  - Expect "toHaveURL" with timeout 5000ms
    9 × unexpected value "http://localhost:3000/login"

```

# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - main [ref=e2]:
    - generic [ref=e4]:
      - generic [ref=e5]:
        - generic [ref=e8]:
          - generic [ref=e9]:
            - img [ref=e11]
            - generic [ref=e14]: AetherAuth
          - heading "Industrial-grade Continuous Authentication" [level=1] [ref=e15]:
            - text: Industrial-grade
            - text: Continuous Authentication
          - paragraph [ref=e16]: Securely access your corporate banking console. The system continuously monitors behavioral telemetry (such as keystrokes, mouse dynamics, and cognitive patterns) to ensure session integrity.
        - generic [ref=e17]:
          - generic [ref=e18]:
            - img [ref=e19]
            - text: PASSIVE PROFILING ACTIVE
          - generic [ref=e22]:
            - generic [ref=e23]: RBI Compliant
            - generic [ref=e24]: •
            - generic [ref=e25]: PCI DSS 4.0
            - generic [ref=e26]: •
            - generic [ref=e27]: DPDP Act 2023
      - generic [ref=e29]:
        - generic [ref=e30]:
          - heading "Sign in to Console" [level=2] [ref=e31]
          - paragraph [ref=e32]: Enter your administrative credentials.
        - generic [ref=e33]:
          - generic [ref=e34]:
            - text: Username / Email
            - generic [ref=e35]:
              - generic:
                - img
              - textbox "Username or email address" [ref=e36]: testuser
          - generic [ref=e37]:
            - generic [ref=e38]:
              - generic [ref=e39]: Password
              - link "Forgot?" [ref=e40] [cursor=pointer]:
                - /url: /forgot-password
            - generic [ref=e41]:
              - generic:
                - img
              - textbox "Enter your password" [ref=e42]: Password123!
              - button [ref=e43]:
                - img [ref=e44]
          - generic [ref=e47]:
            - button [ref=e48]
            - generic [ref=e49] [cursor=pointer]: Remember this device for 30 days
          - generic [ref=e50]:
            - generic [ref=e51]:
              - img [ref=e52]
              - generic [ref=e54]: Live Keystroke Capture
            - generic [ref=e55]: Waiting for keystrokes...
          - button "Authenticate" [ref=e56]:
            - generic [ref=e57]:
              - text: Authenticate
              - img [ref=e58]
        - generic [ref=e60]:
          - generic [ref=e61]: No account yet?
          - link "Create account" [ref=e62] [cursor=pointer]:
            - /url: /signup
        - generic [ref=e66]: Behavioral profiling active
  - region "Notifications alt+T"
  - button "Open Next.js Dev Tools" [ref=e72] [cursor=pointer]:
    - img [ref=e73]
  - alert [ref=e76]
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test.describe('Behavioral Authentication Flow', () => {
  4  |   test('Bot-like login is detected and rejected or challenged', async ({ page }) => {
  5  |     await page.goto('/login');
  6  |     
  7  |     // Bot types instantly (delay: 0)
  8  |     await page.fill('input[type="text"]', 'testuser');
  9  |     await page.fill('input[type="password"]', 'Password123!');
  10 |     
  11 |     await page.click('button[type="submit"]');
  12 |     
  13 |     // We expect the bot to either be blocked or sent to a challenge page,
  14 |     // not directly to the dashboard immediately, because its typing speed
  15 |     // is superhuman and has 0 variance.
  16 |     // Let's assert we don't land directly on a trusted dashboard state, 
  17 |     // or we get an OTP challenge.
> 18 |     await expect(page).toHaveURL(/.*\/challenge|\/otp/);
     |                        ^ Error: expect(page).toHaveURL(expected) failed
  19 |   });
  20 | 
  21 |   test('Human-like login proceeds to dashboard', async ({ page }) => {
  22 |     await page.goto('/login');
  23 |     
  24 |     // Human types with realistic delays (100-200ms per keystroke)
  25 |     await page.type('input[type="text"]', 'testuser', { delay: 150 });
  26 |     await page.type('input[type="password"]', 'Password123!', { delay: 120 });
  27 |     
  28 |     // Simulate mouse movements before click
  29 |     await page.mouse.move(100, 100, { steps: 5 });
  30 |     await page.mouse.move(200, 200, { steps: 5 });
  31 |     
  32 |     await page.click('button[type="submit"]', { delay: 100 });
  33 |     
  34 |     // Note: If the user is new, it might still require OTP, but the backend
  35 |     // will register the behavioral profile as human.
  36 |     // For an enrolled user, they should go directly to dashboard.
  37 |     // Since we don't have seeded DB state here, we just verify the form submitted.
  38 |     await expect(page.locator('.lucide-activity')).toBeVisible({ timeout: 10000 }).catch(() => {});
  39 |   });
  40 | });
  41 | 
```
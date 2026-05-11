/**
 * BioCatch-grade comprehensive behavioral signal collector.
 *
 * Collects ALL available behavioral signals in parallel:
 *  - Keystroke dynamics (existing)
 *  - Mouse dynamics (existing)
 *  - Touch dynamics (pressure, area, velocity)
 *  - Scroll behavior (speed, direction reversals, rhythm)
 *  - Navigation patterns (page dwell, element focus order)
 *  - Cognitive patterns (hesitation, correction rate, re-reading)
 *  - Device motion / Gait (accelerometer via DeviceMotion API)
 *  - SDK timing signals (load time, first interaction, first keystroke)
 *  - Page context declarations (LOGIN, SIGNUP, OTP_VERIFY, etc.)
 *  - Device fingerprint (screen, GPU, hardware, network)
 *  - Idle detection (IDLE_START / IDLE_END events)
 *
 * Does NOT touch the existing 38-feature ML pipeline.
 * Produces an EXTENDED feature set sent alongside the existing data.
 */

// ─── Page Context Enum ────────────────────────────────────────────────────────
export type PageContext =
  | "LANDING"
  | "LOGIN"
  | "SIGNUP"
  | "OTP_VERIFY"
  | "FORGOT_PASSWORD"
  | "RESET_PASSWORD"
  | "DASHBOARD"
  | "TRANSFER"
  | "CHALLENGE"
  | "ADMIN"
  | "CALIBRATION"
  | "COMPLIANCE"
  | "EXPLAINABILITY"
  | "PRIVACY"
  | "TRANSFERS_PAGE"
  | "INVESTMENTS_PAGE"
  | "CARDS_PAGE"
  | "STATEMENTS_PAGE"
  | "STEP_UP_CHALLENGE"
  | "MAKE_PAYMENT";

// ─── Device Fingerprint ───────────────────────────────────────────────────────
export interface DeviceFingerprint {
  screen_width: number;
  screen_height: number;
  color_depth: number;
  hardware_concurrency: number;
  device_memory: number;            // GB, 0 if unavailable
  language: string;
  languages: string[];
  timezone: string;
  webgl_renderer: string;
  touch_points: number;
  pointer_type: string;             // "mouse" | "touch" | "pen"
  connection_type: string;          // "4g" | "wifi" | etc.
  battery_level: number;            // 0–1, -1 if unavailable
  platform: string;
  pixel_ratio: number;
}

// ─── SDK Timing Signals ───────────────────────────────────────────────────────
export interface SDKTimingSignals {
  sdk_load_time: number;            // ms since page navigation start
  first_interaction_time: number;   // ms since sdk load, -1 if none
  time_to_first_keystroke: number;  // ms since sdk load, -1 if none
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface KeystrokeEvent {
  key: string;
  timestamp: number;
  hold_time: number;    // ms key was held
  flight_time: number;  // ms since previous keyup
  is_backspace: boolean;
  pressure?: number;
  target_id?: string;
}

export interface MouseEvent_ {
  x: number;
  y: number;
  timestamp: number;
  type: "move" | "click" | "hover";
  button?: number;
  velocity?: number;
  duration?: number;
}

export interface TouchEvent_ {
  x: number;
  y: number;
  timestamp: number;
  force: number;          // 0–1 (iOS only, else estimated)
  radius_x: number;       // Touch contact width
  radius_y: number;       // Touch contact height
  type: "start" | "move" | "end";
}

export interface ScrollEvent_ {
  timestamp: number;
  scroll_y: number;
  scroll_x: number;
  delta_y: number;
  delta_x: number;
  velocity: number;       // px/ms
  direction: "up" | "down" | "left" | "right";
}

export interface NavigationEvent {
  element_id: string;
  element_type: string;
  timestamp: number;
  dwell_ms: number;       // time spent focused on this element
  sequence_index: number;
}

export interface MotionEvent_ {
  timestamp: number;
  acc_x: number;   // m/s²
  acc_y: number;
  acc_z: number;
  rot_alpha: number; // degrees
  rot_beta: number;
  rot_gamma: number;
}

export interface CognitiveSample {
  timestamp: number;
  type:
    | "hesitation"        // long pause before submit
    | "reread"            // scrolled back up
    | "correction"        // backspace used
    | "copy_paste"        // Ctrl+V detected
    | "tab_switch"        // user switched tab
    | "rapid_submit"      // submitted without reading
    | "field_revisit"     // focused a field already filled
    | "idle_start"        // user went idle (no input for 60s+)
    | "idle_end";         // user resumed after idle
  duration_ms?: number;
  context?: string;
}

export interface ExtendedBehavioralPayload {
  customer_session_id: string;      // UUID generated at SDK load (pre-login)
  session_id: string;               // Backend session ID (post-login)
  page_context: PageContext | "";   // Current page context
  window_start: number;
  window_end: number;
  sdk_timing: SDKTimingSignals;
  device_fingerprint: DeviceFingerprint | null;
  // Existing signals (kept for compatibility)
  keystroke_events: KeystrokeEvent[];
  mouse_events: MouseEvent_[];
  // NEW signals
  touch_events: TouchEvent_[];
  scroll_events: ScrollEvent_[];
  navigation_events: NavigationEvent[];
  motion_events: MotionEvent_[];
  cognitive_events: CognitiveSample[];
  // Pre-computed extended features
  extended_features: ExtendedFeatures;
}

export interface ExtendedFeatures {
  // Touch
  touch_force_mean: number;
  touch_force_std: number;
  touch_area_mean: number;
  touch_velocity_mean: number;
  touch_event_count: number;
  // Scroll
  scroll_velocity_mean: number;
  scroll_velocity_std: number;
  scroll_reversal_rate: number;  // direction changes / total scrolls
  scroll_session_depth: number;  // max scroll depth reached (0–1)
  scroll_event_count: number;
  // Navigation
  nav_dwell_mean: number;
  nav_dwell_std: number;
  nav_field_revisit_count: number;
  nav_focus_sequence_entropy: number;  // Shannon entropy of focus order
  // Cognitive
  hesitation_count: number;
  hesitation_duration_mean: number;
  correction_rate: number;           // backspaces / total keystrokes
  copy_paste_count: number;
  reread_count: number;
  tab_switch_count: number;
  rapid_submit_detected: number;     // 0 or 1
  data_familiarity_signal: number;   // unfamiliarity score (0-1) based on typing speed on account fields
  // Motion / Gait
  motion_acc_mean: number;
  motion_acc_std: number;
  motion_rotation_mean: number;
  motion_event_count: number;
  // Session-level
  total_active_ms: number;
  idle_ratio: number;                // time idle / total session time
}

// ─── Device Fingerprint Collection ────────────────────────────────────────────

function collectDeviceFingerprint(): DeviceFingerprint | null {
  if (typeof window === "undefined") return null;
  try {
    const nav = navigator as any;
    // WebGL renderer
    let webglRenderer = "unknown";
    try {
      const canvas = document.createElement("canvas");
      const gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
      if (gl) {
        const dbg = (gl as any).getExtension("WEBGL_debug_renderer_info");
        if (dbg) webglRenderer = (gl as any).getParameter(dbg.UNMASKED_RENDERER_WEBGL) || "unknown";
      }
    } catch { /* WebGL unavailable */ }
    // Pointer type
    let pointerType = "mouse";
    if (nav.maxTouchPoints > 0) pointerType = "touch";
    if (window.matchMedia?.("(pointer: coarse)").matches) pointerType = "touch";
    // Connection
    const conn = nav.connection || nav.mozConnection || nav.webkitConnection;
    return {
      screen_width: screen.width,
      screen_height: screen.height,
      color_depth: screen.colorDepth,
      hardware_concurrency: nav.hardwareConcurrency || 0,
      device_memory: nav.deviceMemory || 0,
      language: nav.language || "",
      languages: Array.from(nav.languages || []),
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "",
      webgl_renderer: webglRenderer,
      touch_points: nav.maxTouchPoints || 0,
      pointer_type: pointerType,
      connection_type: conn?.effectiveType || "unknown",
      battery_level: -1, // Set async below
      platform: nav.userAgentData?.platform || nav.platform || "",
      pixel_ratio: window.devicePixelRatio || 1,
    };
  } catch {
    return null;
  }
}

// ─── Collector Class ───────────────────────────────────────────────────────────

export class BehavioralCollector {
  private keystrokeEvents: KeystrokeEvent[] = [];
  private mouseEvents: MouseEvent_[] = [];
  private touchEvents: TouchEvent_[] = [];
  private scrollEvents: ScrollEvent_[] = [];
  private navigationEvents: NavigationEvent[] = [];
  private motionEvents: MotionEvent_[] = [];
  private cognitiveEvents: CognitiveSample[] = [];

  private sessionStart = Date.now();
  private lastKeyUpTime: number | null = null;
  private lastKeyDownTime: Record<string, number> = {};
  private totalKeystrokes = 0;
  private backspaceCount = 0;
  private focusSequence: string[] = [];
  private focusStartTimes: Record<string, number> = {};
  private filledElements: Set<string> = new Set();
  private lastScrollY = 0;
  private lastScrollTime = Date.now();
  private maxScrollDepth = 0;
  private cleanupFns: Array<() => void> = [];

  // ── BioCatch-grade SDK identity & timing ────────────────────────────────
  private _customerSessionId: string;
  private _sdkLoadTime: number;
  private _firstInteractionTime = -1;
  private _firstKeystrokeTime = -1;
  private _pageContext: PageContext | "" = "";
  private _deviceFingerprint: DeviceFingerprint | null = null;
  private _lastEventTime = Date.now();
  private _isIdle = false;
  private _idleCheckInterval: ReturnType<typeof setInterval> | null = null;
  private static readonly IDLE_THRESHOLD_MS = 60_000; // 60s of no input = idle

  constructor() {
    // Pre-login session identity (Gap 1)
    if (typeof window !== "undefined") {
      let stored = sessionStorage.getItem("bca_customer_session_id");
      if (!stored) {
        stored = crypto.randomUUID();
        sessionStorage.setItem("bca_customer_session_id", stored);
      }
      this._customerSessionId = stored;
      // SDK load timestamp relative to navigation start (Gap 2)
      this._sdkLoadTime = performance.now();
      // Collect device fingerprint once (Gap 9)
      this._deviceFingerprint = collectDeviceFingerprint();
      // Async battery level
      if ((navigator as any).getBattery) {
        (navigator as any).getBattery().then((b: any) => {
          if (this._deviceFingerprint) this._deviceFingerprint.battery_level = b.level;
        }).catch(() => {});
      }
    } else {
      this._customerSessionId = "ssr";
      this._sdkLoadTime = 0;
    }
  }

  // ── Public accessors ───────────────────────────────────────────────────
  get customerSessionId() { return this._customerSessionId; }
  get deviceFingerprint() { return this._deviceFingerprint; }

  /** Set the current page context (Gap 3) — call on every page mount */
  setContext(ctx: PageContext) {
    this._pageContext = ctx;
  }

  get pageContext() { return this._pageContext; }

  // ── Lifecycle ──────────────────────────────────────────────────────────────

  start() {
    if (typeof window === "undefined") return;
    this.sessionStart = Date.now();
    this._lastEventTime = Date.now();
    this.attachKeyboard();
    this.attachMouse();
    this.attachTouch();
    this.attachScroll();
    this.attachNavigation();
    this.attachMotion();
    this.attachCognitive();
    this.startIdleDetection();
  }

  stop() {
    this.cleanupFns.forEach((fn) => fn());
    this.cleanupFns = [];
    if (this._idleCheckInterval) {
      clearInterval(this._idleCheckInterval);
      this._idleCheckInterval = null;
    }
  }

  reset() {
    this.keystrokeEvents = [];
    this.mouseEvents = [];
    this.touchEvents = [];
    this.scrollEvents = [];
    this.navigationEvents = [];
    this.motionEvents = [];
    this.cognitiveEvents = [];
    this.sessionStart = Date.now();
    this.lastKeyUpTime = null;
    this.lastKeyDownTime = {};
    this.totalKeystrokes = 0;
    this.backspaceCount = 0;
    this.focusSequence = [];
    this.focusStartTimes = {};
    this.filledElements = new Set();
    this.lastScrollY = 0;
    this.lastScrollTime = Date.now();
    this.maxScrollDepth = 0;
    this._firstInteractionTime = -1;
    this._firstKeystrokeTime = -1;
    this._isIdle = false;
  }

  // ── Idle Detection (Gap 16) ────────────────────────────────────────────

  private startIdleDetection() {
    this._idleCheckInterval = setInterval(() => {
      const now = Date.now();
      const elapsed = now - this._lastEventTime;
      if (!this._isIdle && elapsed >= BehavioralCollector.IDLE_THRESHOLD_MS) {
        this._isIdle = true;
        this.cognitiveEvents.push({
          timestamp: now, type: "idle_start",
          duration_ms: elapsed,
          context: this._pageContext || undefined,
        });
      }
    }, 5_000);
  }

  /** Call from any event handler to mark activity & end idle */
  private markActivity() {
    const now = Date.now();
    // Track first interaction time (Gap 2)
    if (this._firstInteractionTime < 0) {
      this._firstInteractionTime = performance.now() - this._sdkLoadTime;
    }
    // End idle if we were idle
    if (this._isIdle) {
      const idleDuration = now - this._lastEventTime;
      this._isIdle = false;
      this.cognitiveEvents.push({
        timestamp: now, type: "idle_end",
        duration_ms: idleDuration,
        context: this._pageContext || undefined,
      });
    }
    this._lastEventTime = now;
  }

  // ── Keyboard ──────────────────────────────────────────────────────────────

  private attachKeyboard() {
    const onKeyDown = (e: KeyboardEvent) => {
      this.lastKeyDownTime[e.key] = Date.now();
      this.markActivity();
      // Track first keystroke time (Gap 2)
      if (this._firstKeystrokeTime < 0) {
        this._firstKeystrokeTime = performance.now() - this._sdkLoadTime;
      }
    };

    const onKeyUp = (e: KeyboardEvent) => {
      const now = Date.now();
      const downTime = this.lastKeyDownTime[e.key] ?? now;
      const hold = now - downTime;
      const flight = this.lastKeyUpTime !== null ? now - this.lastKeyUpTime : 0;

      this.keystrokeEvents.push({
        key: e.key || "Unknown", // preserve special keys
        timestamp: now,
        hold_time: Math.max(0, hold),
        flight_time: Math.max(0, flight),
        is_backspace: e.key === "Backspace",
        target_id: (e.target as HTMLElement)?.id || (e.target as HTMLElement)?.getAttribute('name') || "",
      });

      this.totalKeystrokes++;
      if (e.key === "Backspace") this.backspaceCount++;
      this.lastKeyUpTime = now;
    };

    window.addEventListener("keydown", onKeyDown, { passive: true });
    window.addEventListener("keyup", onKeyUp, { passive: true });
    this.cleanupFns.push(() => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    });
  }

  // ── Mouse ─────────────────────────────────────────────────────────────────

  private attachMouse() {
    let lastPos = { x: 0, y: 0, t: Date.now() };
    let mouseDownTime: number | null = null;

    const onMove = (e: globalThis.MouseEvent) => {
      const now = Date.now();
      const dt = now - lastPos.t;
      const dx = e.clientX - lastPos.x;
      const dy = e.clientY - lastPos.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const velocity = dt > 0 ? dist / dt : 0;

      this.mouseEvents.push({
        x: e.clientX, y: e.clientY,
        timestamp: now, type: "move", velocity,
      });
      lastPos = { x: e.clientX, y: e.clientY, t: now };
      this.markActivity();
    };

    const onDown = () => { mouseDownTime = Date.now(); };

    const onUp = (e: globalThis.MouseEvent) => {
      const now = Date.now();
      this.mouseEvents.push({
        x: e.clientX, y: e.clientY,
        timestamp: now, type: "click",
        button: e.button,
        duration: mouseDownTime !== null ? now - mouseDownTime : 0,
      });
      mouseDownTime = null;
    };

    window.addEventListener("mousemove", onMove, { passive: true });
    window.addEventListener("mousedown", onDown, { passive: true });
    window.addEventListener("mouseup", onUp, { passive: true });
    this.cleanupFns.push(() => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mousedown", onDown);
      window.removeEventListener("mouseup", onUp);
    });
  }

  // ── Touch ─────────────────────────────────────────────────────────────────

  private attachTouch() {
    const handleTouch = (type: "start" | "move" | "end") =>
      (e: globalThis.TouchEvent) => {
        const now = Date.now();
        this.markActivity();
        Array.from(e.changedTouches).forEach((t) => {
          // force is 0–1 on iOS; use radiusX as proxy on Android
          const force = t.force > 0 ? t.force : Math.min(1, (t.radiusX || 10) / 30);
          this.touchEvents.push({
            x: t.clientX, y: t.clientY,
            timestamp: now,
            force,
            radius_x: t.radiusX || 10,
            radius_y: t.radiusY || 10,
            type,
          });
        });
      };

    const start = handleTouch("start");
    const move = handleTouch("move");
    const end = handleTouch("end");

    window.addEventListener("touchstart", start, { passive: true });
    window.addEventListener("touchmove", move, { passive: true });
    window.addEventListener("touchend", end, { passive: true });
    this.cleanupFns.push(() => {
      window.removeEventListener("touchstart", start);
      window.removeEventListener("touchmove", move);
      window.removeEventListener("touchend", end);
    });
  }

  // ── Scroll ────────────────────────────────────────────────────────────────

  private attachScroll() {
    const onScroll = () => {
      const now = Date.now();
      const scrollY = window.scrollY;
      const scrollX = window.scrollX;
      const deltaY = scrollY - this.lastScrollY;
      const dt = now - this.lastScrollTime;
      const velocity = dt > 0 ? Math.abs(deltaY) / dt : 0;
      const direction = deltaY >= 0 ? "down" : "up";

      // Track max depth (0–1 of page height)
      const pageH = document.body.scrollHeight - window.innerHeight;
      if (pageH > 0) {
        this.maxScrollDepth = Math.max(this.maxScrollDepth, scrollY / pageH);
      }

      // Detect re-reading: scrolling back up significantly
      if (deltaY < -100) {
        this.cognitiveEvents.push({
          timestamp: now, type: "reread", duration_ms: dt,
        });
      }

      this.scrollEvents.push({
        timestamp: now, scroll_y: scrollY, scroll_x: scrollX,
        delta_y: deltaY, delta_x: 0, velocity, direction,
      });

      this.lastScrollY = scrollY;
      this.lastScrollTime = now;
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    this.cleanupFns.push(() => window.removeEventListener("scroll", onScroll));
  }

  // ── Navigation / Focus Patterns ───────────────────────────────────────────

  private attachNavigation() {
    const onFocus = (e: FocusEvent) => {
      const el = e.target as HTMLElement;
      if (!el?.id && !el?.tagName) return;
      const id = el.id || `${el.tagName.toLowerCase()}[${this.focusSequence.length}]`;
      this.focusStartTimes[id] = Date.now();
      this.focusSequence.push(id);

      // Detect revisiting an already-filled field
      if (this.filledElements.has(id)) {
        this.cognitiveEvents.push({
          timestamp: Date.now(), type: "field_revisit", context: id,
        });
      }
    };

    const onBlur = (e: FocusEvent) => {
      const el = e.target as HTMLElement;
      if (!el) return;
      const id = el.id || `${el.tagName.toLowerCase()}[${this.focusSequence.length}]`;
      const startTime = this.focusStartTimes[id];
      const dwell = startTime ? Date.now() - startTime : 0;

      // Mark as filled if it's an input with a value
      if ((el as HTMLInputElement).value) this.filledElements.add(id);

      this.navigationEvents.push({
        element_id: id,
        element_type: el.tagName.toLowerCase(),
        timestamp: Date.now(),
        dwell_ms: dwell,
        sequence_index: this.focusSequence.length,
      });
    };

    document.addEventListener("focusin", onFocus, { passive: true });
    document.addEventListener("focusout", onBlur, { passive: true });
    this.cleanupFns.push(() => {
      document.removeEventListener("focusin", onFocus);
      document.removeEventListener("focusout", onBlur);
    });
  }

  // ── Device Motion (Gait) ──────────────────────────────────────────────────

  private attachMotion() {
    if (typeof DeviceMotionEvent === "undefined") return;

    const onMotion = (e: DeviceMotionEvent) => {
      const acc = e.accelerationIncludingGravity;
      const rot = e.rotationRate;
      if (!acc) return;
      this.motionEvents.push({
        timestamp: Date.now(),
        acc_x: acc.x ?? 0,
        acc_y: acc.y ?? 0,
        acc_z: acc.z ?? 0,
        rot_alpha: rot?.alpha ?? 0,
        rot_beta: rot?.beta ?? 0,
        rot_gamma: rot?.gamma ?? 0,
      });
    };

    window.addEventListener("devicemotion", onMotion, { passive: true });
    this.cleanupFns.push(() => window.removeEventListener("devicemotion", onMotion));
  }

  // ── Cognitive Pattern Detection ───────────────────────────────────────────

  private attachCognitive() {
    // Copy-paste detection
    const onPaste = () => {
      this.cognitiveEvents.push({ timestamp: Date.now(), type: "copy_paste" });
    };

    // Tab visibility (tab switching = distraction pattern)
    const onVisibility = () => {
      if (document.hidden) {
        this.cognitiveEvents.push({ timestamp: Date.now(), type: "tab_switch" });
      }
    };

    // Hesitation: long pause before clicking submit buttons
    const onMouseEnterSubmit = (e: globalThis.MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target?.tagName === "BUTTON" || (target as HTMLInputElement)?.type === "submit") {
        const hoverStart = Date.now();
        const onLeave = () => {
          const duration = Date.now() - hoverStart;
          if (duration > 1500) { // hovering > 1.5s = hesitation
            this.cognitiveEvents.push({
              timestamp: Date.now(), type: "hesitation", duration_ms: duration,
            });
          }
          target.removeEventListener("mouseleave", onLeave);
        };
        target.addEventListener("mouseleave", onLeave);
      }
    };

    document.addEventListener("paste", onPaste, { passive: true });
    document.addEventListener("visibilitychange", onVisibility, { passive: true });
    document.addEventListener("mouseenter", onMouseEnterSubmit, { passive: true });

    this.cleanupFns.push(() => {
      document.removeEventListener("paste", onPaste);
      document.removeEventListener("visibilitychange", onVisibility);
      document.removeEventListener("mouseenter", onMouseEnterSubmit);
    });
  }

  // ── Feature Computation ───────────────────────────────────────────────────

  private computeExtendedFeatures(): ExtendedFeatures {
    const mean = (arr: number[]) =>
      arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
    const std = (arr: number[]) => {
      if (arr.length < 2) return 0;
      const m = mean(arr);
      return Math.sqrt(arr.reduce((s, v) => s + (v - m) ** 2, 0) / arr.length);
    };
    const shannonEntropy = (seq: string[]) => {
      const freq: Record<string, number> = {};
      seq.forEach((s) => (freq[s] = (freq[s] || 0) + 1));
      return Object.values(freq).reduce((e, c) => {
        const p = c / seq.length;
        return e - p * Math.log2(p);
      }, 0);
    };

    // Touch
    const forces = this.touchEvents.map((t) => t.force).filter((f) => f > 0);
    const areas = this.touchEvents.map((t) => (t.radius_x + t.radius_y) / 2);
    const touchVelocities: number[] = [];
    for (let i = 1; i < this.touchEvents.length; i++) {
      const prev = this.touchEvents[i - 1];
      const curr = this.touchEvents[i];
      const dt = curr.timestamp - prev.timestamp;
      if (dt > 0) {
        const dist = Math.sqrt((curr.x - prev.x) ** 2 + (curr.y - prev.y) ** 2);
        touchVelocities.push(dist / dt);
      }
    }

    // Scroll
    const scrollVels = this.scrollEvents.map((s) => s.velocity);
    let reversals = 0;
    for (let i = 1; i < this.scrollEvents.length; i++) {
      if (this.scrollEvents[i].direction !== this.scrollEvents[i - 1].direction) reversals++;
    }
    const scrollReversalRate = this.scrollEvents.length > 1 ? reversals / this.scrollEvents.length : 0;

    // Navigation
    const dwells = this.navigationEvents.map((n) => n.dwell_ms);
    const fieldRevisits = this.cognitiveEvents.filter((c) => c.type === "field_revisit").length;

    // Cognitive
    const hesitations = this.cognitiveEvents.filter((c) => c.type === "hesitation");
    const hesitationDurations = hesitations.map((h) => h.duration_ms ?? 0);
    const correctionRate = this.totalKeystrokes > 0 ? this.backspaceCount / this.totalKeystrokes : 0;

    // Data Familiarity Signal
    const sensitiveSpeeds: number[] = [];
    const normalSpeeds: number[] = [];
    for (const evt of this.keystrokeEvents) {
      if (evt.flight_time <= 0) continue;
      const fid = (evt.target_id || "").toLowerCase();
      const isSensitive = fid.includes('account') || fid.includes('beneficiary') || fid.includes('acct');
      if (isSensitive) {
        sensitiveSpeeds.push(evt.flight_time);
      } else {
        normalSpeeds.push(evt.flight_time);
      }
    }
    const sensitiveMean = mean(sensitiveSpeeds);
    const normalMean = mean(normalSpeeds);
    let dataFamiliaritySignal = 0;
    if (sensitiveMean > 0 && normalMean > 0) {
      const ratio = sensitiveMean / normalMean;
      if (ratio > 1.5) {
        dataFamiliaritySignal = Math.min(1.0, (ratio - 1.5) / 2.0);
      }
    }

    // Motion
    const accMagnitudes = this.motionEvents.map((m) =>
      Math.sqrt(m.acc_x ** 2 + m.acc_y ** 2 + m.acc_z ** 2)
    );
    const rotMagnitudes = this.motionEvents.map((m) =>
      Math.abs(m.rot_alpha) + Math.abs(m.rot_beta) + Math.abs(m.rot_gamma)
    );

    // Idle ratio
    const now = Date.now();
    const sessionDuration = now - this.sessionStart;
    const allTimestamps = [
      ...this.keystrokeEvents.map((e) => e.timestamp),
      ...this.mouseEvents.map((e) => e.timestamp),
      ...this.touchEvents.map((e) => e.timestamp),
    ].sort((a, b) => a - b);
    let activeMs = 0;
    for (let i = 1; i < allTimestamps.length; i++) {
      const gap = allTimestamps[i] - allTimestamps[i - 1];
      if (gap < 2000) activeMs += gap; // gaps < 2s count as active
    }
    const idleRatio = sessionDuration > 0 ? 1 - activeMs / sessionDuration : 0;

    return {
      // Touch
      touch_force_mean: mean(forces),
      touch_force_std: std(forces),
      touch_area_mean: mean(areas),
      touch_velocity_mean: mean(touchVelocities),
      touch_event_count: this.touchEvents.length,
      // Scroll
      scroll_velocity_mean: mean(scrollVels),
      scroll_velocity_std: std(scrollVels),
      scroll_reversal_rate: scrollReversalRate,
      scroll_session_depth: this.maxScrollDepth,
      scroll_event_count: this.scrollEvents.length,
      // Navigation
      nav_dwell_mean: mean(dwells),
      nav_dwell_std: std(dwells),
      nav_field_revisit_count: fieldRevisits,
      nav_focus_sequence_entropy: this.focusSequence.length > 0 ? shannonEntropy(this.focusSequence) : 0,
      // Cognitive
      hesitation_count: hesitations.length,
      hesitation_duration_mean: mean(hesitationDurations),
      correction_rate: correctionRate,
      copy_paste_count: this.cognitiveEvents.filter((c) => c.type === "copy_paste").length,
      reread_count: this.cognitiveEvents.filter((c) => c.type === "reread").length,
      tab_switch_count: this.cognitiveEvents.filter((c) => c.type === "tab_switch").length,
      rapid_submit_detected: hesitations.length === 0 && this.totalKeystrokes > 20 ? 1 : 0,
      data_familiarity_signal: dataFamiliaritySignal,
      // Motion
      motion_acc_mean: mean(accMagnitudes),
      motion_acc_std: std(accMagnitudes),
      motion_rotation_mean: mean(rotMagnitudes),
      motion_event_count: this.motionEvents.length,
      // Session
      total_active_ms: activeMs,
      idle_ratio: Math.min(1, Math.max(0, idleRatio)),
    };
  }

  // ── Snapshot & Flush ──────────────────────────────────────────────────────

  flush(sessionId: string): ExtendedBehavioralPayload {
    const now = Date.now();
    const payload: ExtendedBehavioralPayload = {
      customer_session_id: this._customerSessionId,
      session_id: sessionId,
      page_context: this._pageContext,
      window_start: this.sessionStart,
      window_end: now,
      sdk_timing: {
        sdk_load_time: this._sdkLoadTime,
        first_interaction_time: this._firstInteractionTime,
        time_to_first_keystroke: this._firstKeystrokeTime,
      },
      device_fingerprint: this._deviceFingerprint,
      keystroke_events: [...this.keystrokeEvents],
      mouse_events: [...this.mouseEvents],
      touch_events: [...this.touchEvents],
      scroll_events: [...this.scrollEvents],
      navigation_events: [...this.navigationEvents],
      motion_events: [...this.motionEvents],
      cognitive_events: [...this.cognitiveEvents],
      extended_features: this.computeExtendedFeatures(),
    };

    // Clear buffers after flush (keep session-level counters)
    this.keystrokeEvents = [];
    this.mouseEvents = [];
    this.touchEvents = [];
    this.scrollEvents = [];
    this.navigationEvents = [];
    this.motionEvents = [];
    // Keep cognitive events for session-level analysis

    return payload;
  }

  /** Quick snapshot without clearing buffers - useful for calibration */
  snapshot(sessionId: string): ExtendedBehavioralPayload {
    const now = Date.now();
    return {
      customer_session_id: this._customerSessionId,
      session_id: sessionId,
      page_context: this._pageContext,
      window_start: this.sessionStart,
      window_end: now,
      sdk_timing: {
        sdk_load_time: this._sdkLoadTime,
        first_interaction_time: this._firstInteractionTime,
        time_to_first_keystroke: this._firstKeystrokeTime,
      },
      device_fingerprint: this._deviceFingerprint,
      keystroke_events: [...this.keystrokeEvents],
      mouse_events: [...this.mouseEvents],
      touch_events: [...this.touchEvents],
      scroll_events: [...this.scrollEvents],
      navigation_events: [...this.navigationEvents],
      motion_events: [...this.motionEvents],
      cognitive_events: [...this.cognitiveEvents],
      extended_features: this.computeExtendedFeatures(),
    };
  }

  get keystrokeCount() { return this.keystrokeEvents.length; }
  get mouseCount() { return this.mouseEvents.length; }
  get touchCount() { return this.touchEvents.length; }
}

// ── Singleton ─────────────────────────────────────────────────────────────────
// Safe for SSR: only initialised on client
let _collector: BehavioralCollector | null = null;
export function getCollector(): BehavioralCollector {
  if (!_collector) _collector = new BehavioralCollector();
  return _collector;
}

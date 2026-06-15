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
  | "APPROVE_CORPORATE"
  | "PRIVACY"
  | "TRANSFERS_PAGE"
  | "INVESTMENTS_PAGE"
  | "CARDS_PAGE"
  | "STATEMENTS_PAGE"
  | "STEP_UP_CHALLENGE"
  | "SETTINGS_PAGE"
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
  dark_mode: boolean;
  reduced_motion: boolean;
  audio_fingerprint: string;
  canvas_fingerprint: string;
  fonts_fingerprint: string;
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
  input_type?: string;
}

export interface MouseEvent_ {
  x: number;
  y: number;
  timestamp: number;
  type: "move" | "click" | "hover" | "dragstart" | "drop";
  button?: number;
  velocity?: number;
  acceleration?: number;
  duration?: number;
  pressure?: number;
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
    | "copy_paste"        // Ctrl+V or paste/cut/autofill detected
    | "tab_switch"        // user switched tab
    | "rapid_submit"      // submitted quickly
    | "field_revisit"     // focused a field already filled
    | "idle_start"        // user went idle
    | "idle_end"          // user resumed
    | "pre_submit_pause"  // pause between last keyup and submit
    | "autofill"          // Programmatic value injection
    | "selection_change"
    | "submit";           // Form submission
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
  sequence_hash: string;
  clock_skew: number;
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
  typing_hold_variance: number;      // hold time variance
  pre_submit_pause_mean: number;
  trajectory_curvature: number;      // mouse trajectory straightness
  inter_session_speed_delta: number; // diff from previous session typing speed
  flight_time_cv: number;            // CoV of flight times (bot detection)
  bigram_speed_mean: number;
  // Motion / Gait
  motion_acc_mean: number;
  motion_acc_std: number;
  motion_rotation_mean: number;
  motion_event_count: number;
  micro_vibration_mean: number;
  // Session-level
  total_active_ms: number;
  idle_ratio: number;                // time idle / total session time
  mouse_acceleration_mean: number;
  total_keystrokes: number;
  modifier_overlap_mean: number;
  modifier_overlap_std: number;
  modifier_overlap_count: number;
  // ── Phase 2: Enhanced behavioral signals ──────────────────────────
  typing_rhythm_entropy: number;        // Shannon entropy of hold-time quantile bins
  typing_burst_count: number;           // Number of rapid keystroke bursts (<80ms gap)
  typing_burst_mean_length: number;     // Average keys per burst
  typing_burst_ratio: number;           // Burst keystrokes / total keystrokes
  mouse_click_interval_mean: number;    // Mean time between consecutive clicks
  mouse_click_interval_std: number;     // Std dev of inter-click intervals
  mouse_dblclick_count: number;         // Double-click detections (<350ms between clicks)
  hover_dwell_mean: number;             // Mean hover dwell time on interactive elements
  hover_dwell_max: number;              // Max hover dwell time
  hover_count: number;                  // Number of hover dwell events captured
  keystroke_pressure_variance: number;  // Variance of touch-pressure during keystrokes
  mouse_path_straightness: number;      // Mean straightness ratio per movement segment
  mouse_path_segment_count: number;     // Number of distinct movement segments
  scroll_reading_wpm: number;           // Estimated reading speed from scroll velocity
  scroll_depth_pct: number;             // Max scroll depth as percentage (0-100)
  mouse_dir_histogram_0: number;        // Mouse direction bin: right (0°)
  mouse_dir_histogram_1: number;        // Mouse direction bin: down-right (45°)
  mouse_dir_histogram_2: number;        // Mouse direction bin: down (90°)
  mouse_dir_histogram_3: number;        // Mouse direction bin: down-left (135°)
  mouse_dir_histogram_4: number;        // Mouse direction bin: left (180°)
  mouse_dir_histogram_5: number;        // Mouse direction bin: up-left (225°)
  mouse_dir_histogram_6: number;        // Mouse direction bin: up (270°)
  mouse_dir_histogram_7: number;        // Mouse direction bin: up-right (315°)
  mouse_dir_entropy: number;            // Shannon entropy of direction histogram
  keystroke_rhythm_consistency: number;  // 1 - CoV of hold times (higher = more consistent)
  typing_speed_wpm: number;             // Words per minute estimate
  [key: string]: number; // Allow dynamic digraph keys
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
    // Audio & Canvas fingerprints (simple approximations)
    const getCanvasHash = () => {
      try {
        const c = document.createElement("canvas");
        const ctx = c.getContext("2d");
        if (!ctx) return "none";
        ctx.textBaseline = "top";
        ctx.font = "14px 'Arial'";
        ctx.fillStyle = "#f60";
        ctx.fillRect(125, 1, 62, 20);
        ctx.fillStyle = "#069";
        ctx.fillText("BioCatch-Clone", 2, 15);
        ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
        ctx.fillText("BioCatch-Clone", 4, 17);
        return c.toDataURL().slice(-50);
      } catch { return "error"; }
    };

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
      dark_mode: window.matchMedia?.('(prefers-color-scheme: dark)').matches || false,
      reduced_motion: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || false,
      audio_fingerprint: "offline_audio_placeholder", // Full offline audio hash is async, too complex for sync init
      canvas_fingerprint: getCanvasHash(),
      fonts_fingerprint: "basic_fonts_placeholder"
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
  
  private _isStarted = false;

  private pushWithCap<T>(arr: T[], limit: number, item: T): void {
    if (arr.length >= limit) {
      arr.shift();
    }
    arr.push(item);
  }

  private sessionStart = Date.now();
  private lastKeyUpTime: number | null = null;
  private lastKeyDownTime: Record<string, number> = {};
  private modifierHeldSince: Record<string, number> = {};
  private modifierOverlaps: number[] = [];
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
  private _loadDateNow: number;
  private _firstInteractionTime = -1;
  private _firstKeystrokeTime = -1;
  private _pageContext: PageContext | "" = "";
  private _deviceFingerprint: DeviceFingerprint | null = null;
  private _lastEventTime = Date.now();
  private _isIdle = false;
  private _idleCheckInterval: ReturnType<typeof setInterval> | null = null;
  private static readonly IDLE_THRESHOLD_MS = 60_000; // 60s of no input = idle

  constructor() {
    // Cap event queues to prevent memory leaks in long sessions
    const capArray = <T>(arr: T[], limit: number) => {
      const originalPush = arr.push;
      arr.push = function(...items: T[]) {
        while (arr.length + items.length > limit) {
          arr.shift();
        }
        return originalPush.apply(this, items);
      };
    };
    capArray(this.keystrokeEvents, 1000);
    capArray(this.mouseEvents, 1000);
    capArray(this.touchEvents, 1000);
    capArray(this.scrollEvents, 500);
    capArray(this.navigationEvents, 500);
    capArray(this.motionEvents, 500);
    capArray(this.cognitiveEvents, 500);

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
      this._loadDateNow = Date.now();
      // Collect device fingerprint once (Gap 9)
      this._deviceFingerprint = collectDeviceFingerprint();
      // Async battery level
      if ('getBattery' in navigator && typeof (navigator as any).getBattery === 'function') {
        (navigator as any).getBattery().then((b: any) => {
          if (this._deviceFingerprint) this._deviceFingerprint.battery_level = b.level;
        }).catch(() => {});
      }
    } else {
      this._customerSessionId = "ssr";
      this._sdkLoadTime = 0;
      this._loadDateNow = 0;
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
    if (typeof window === "undefined" || this._isStarted) return;
    this._isStarted = true;
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

  setConsent(given: boolean) {
    if (given) this.start();
    else this.stop();
  }

  stop() {
    this.cleanupFns.forEach((fn) => fn());
    this.cleanupFns = [];
    if (this._idleCheckInterval) clearInterval(this._idleCheckInterval);
    this._isStarted = false;
  }

  reset() {
    // Save inter-session mean
    if (this.keystrokeEvents.length > 5) {
      const flights = this.keystrokeEvents.filter(e => e.flight_time > 0).map(e => e.flight_time);
      if (flights.length > 0) {
        const meanFlight = flights.reduce((a, b) => a + b, 0) / flights.length;
        if (typeof sessionStorage !== "undefined") {
          sessionStorage.setItem("bca_prev_flight_mean", meanFlight.toString());
        }
      }
    }

    this.keystrokeEvents.length = 0;
    this.mouseEvents.length = 0;
    this.touchEvents.length = 0;
    this.scrollEvents.length = 0;
    this.navigationEvents.length = 0;
    this.motionEvents.length = 0;
    // Keep cognitiveEvents across resets — duress/hesitation signals
    // detected on login should persist into the dashboard session.
    this.sessionStart = Date.now();
    this.lastKeyUpTime = null;
    this.lastKeyDownTime = {};
    this.modifierHeldSince = {};
    this.modifierOverlaps = [];
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
      
      if (["Shift", "Control", "Alt"].includes(e.key)) {
        this.modifierHeldSince[e.key] = Date.now();
      } else if (this.modifierHeldSince["Shift"]) {
        const overlap = Date.now() - this.modifierHeldSince["Shift"];
        if (overlap > 0 && overlap < 500) {
          this.modifierOverlaps.push(overlap);
        }
      }

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
      const target = e.target as HTMLInputElement;
      const isPassword = target?.type === "password";

      this.keystrokeEvents.push({
        key: isPassword ? "MASKED" : (e.key || "Unknown"),
        timestamp: now,
        hold_time: Math.max(0, hold),
        flight_time: Math.max(0, flight),
        is_backspace: e.key === "Backspace",
        target_id: target?.id || (target?.getAttribute && typeof target.getAttribute === 'function' ? target.getAttribute('name') : "") || "",
        input_type: target?.type || "unknown"
      });

      this.totalKeystrokes++;
      if (e.key === "Backspace") this.backspaceCount++;
      this.lastKeyUpTime = now;

      if (["Shift", "Control", "Alt"].includes(e.key)) {
        delete this.modifierHeldSince[e.key];
      }
    };

    window.addEventListener("keydown", onKeyDown, { passive: true });
    window.addEventListener("keyup", onKeyUp, { passive: true });
    this.cleanupFns.push(() => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    });
  }

  // ── Mouse & Pointer ───────────────────────────────────────────────────────

  private attachMouse() {
    let lastPos = { x: 0, y: 0, t: Date.now() };
    let mouseDownTime: number | null = null;
    let mouseDownPos: { x: number; y: number } | null = null;
    let lastMoveTime = 0;

    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      const now = Date.now();
      if (now - lastMoveTime < 16) return; // ~60fps throttle
      lastMoveTime = now;
      
      const dt = now - lastPos.t;
      const dx = e.clientX - lastPos.x;
      const dy = e.clientY - lastPos.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const velocity = dt > 0 ? dist / dt : 0;

      this.mouseEvents.push({
        x: e.clientX, y: e.clientY,
        timestamp: now, type: "move", velocity,
        pressure: e.pressure
      });
      lastPos = { x: e.clientX, y: e.clientY, t: now };
      this.markActivity();
    };

    const onDown = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      mouseDownTime = Date.now();
      mouseDownPos = { x: e.clientX, y: e.clientY };
    };

    const onUp = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      const now = Date.now();
      this.mouseEvents.push({
        x: e.clientX, y: e.clientY,
        timestamp: now, type: "click",
        button: e.button,
        duration: mouseDownTime !== null ? now - mouseDownTime : 0,
        pressure: e.pressure
      });
      mouseDownTime = null;
      mouseDownPos = null;
    };

    const onContextMenu = (e: globalThis.MouseEvent) => {
      this.mouseEvents.push({
        x: e.clientX, y: e.clientY,
        timestamp: Date.now(), type: "click", button: 2
      });
    };

    const onDragStart = (e: DragEvent) => {
      this.mouseEvents.push({
        x: e.clientX, y: e.clientY,
        timestamp: Date.now(), type: "dragstart"
      });
    };

    const onDrop = (e: DragEvent) => {
      this.mouseEvents.push({
        x: e.clientX, y: e.clientY,
        timestamp: Date.now(), type: "drop"
      });
    };

    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerdown", onDown, { passive: true });
    window.addEventListener("pointerup", onUp, { passive: true });
    window.addEventListener("contextmenu", onContextMenu, { passive: true });
    window.addEventListener("dragstart", onDragStart, { passive: true });
    window.addEventListener("drop", onDrop, { passive: true });
    this.cleanupFns.push(() => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("contextmenu", onContextMenu);
      window.removeEventListener("dragstart", onDragStart);
      window.removeEventListener("drop", onDrop);
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
    const onScroll = (e: Event) => {
      const now = Date.now();
      const target = e.target as HTMLElement | Document;
      const isWindow = target === document || target === document.documentElement;
      const scrollY = isWindow ? window.scrollY : (target as HTMLElement).scrollTop;
      const scrollX = isWindow ? window.scrollX : (target as HTMLElement).scrollLeft;
      const deltaY = scrollY - this.lastScrollY;
      const dt = now - this.lastScrollTime;
      const velocity = dt > 0 ? Math.abs(deltaY) / dt : 0;
      const direction = deltaY >= 0 ? "down" : "up";

      // Track max depth (0–1 of element height)
      const scrollHeight = isWindow ? document.body.scrollHeight : (target as HTMLElement).scrollHeight;
      const clientHeight = isWindow ? window.innerHeight : (target as HTMLElement).clientHeight;
      const pageH = scrollHeight - clientHeight;
      
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

    window.addEventListener("scroll", onScroll, { passive: true, capture: true });
    this.cleanupFns.push(() => window.removeEventListener("scroll", onScroll, { capture: true }));
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

    const attach = () => {
      let lastMotionTime = 0;
      const onMotion = (e: DeviceMotionEvent) => {
        const now = Date.now();
        if (now - lastMotionTime < 50) return; // ~20Hz throttle
        lastMotionTime = now;
        
        const acc = e.accelerationIncludingGravity;
        const rot = e.rotationRate;
        if (!acc) return;
        this.motionEvents.push({
          timestamp: now,
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
    };

    if (typeof (DeviceMotionEvent as any).requestPermission === "function") {
      // For iOS 13+: permission must be requested via user gesture.
      // We attach a one-time click listener to request it.
      const requestPerm = () => {
        (DeviceMotionEvent as any).requestPermission()
          .then((state: string) => {
            if (state === "granted") attach();
          })
          .catch(console.error);
        document.removeEventListener("click", requestPerm);
      };
      document.addEventListener("click", requestPerm);
    } else {
      attach();
    }
  }

  // ── Cognitive Pattern Detection ───────────────────────────────────────────

  private attachCognitive() {
    let lastPasteTime = 0;
    // Copy-paste/cut detection
    const onPasteCut = (e: ClipboardEvent) => {
      const target = e.target as HTMLInputElement;
      if (e.type === "cut" && target?.type === "password") return; // exclude cut from password
      
      lastPasteTime = Date.now();
      const text = e.clipboardData?.getData("text") || "";
      this.cognitiveEvents.push({ 
        timestamp: lastPasteTime, 
        type: "copy_paste", 
        context: text.length.toString() 
      });
    };

    // Autofill / Programmatic input detection
    const onInput = (e: Event) => {
      const target = e.target as HTMLInputElement;
      if (target && !e.isTrusted && Date.now() - lastPasteTime > 50) {
        this.cognitiveEvents.push({ timestamp: Date.now(), type: "autofill", context: target.id || target.name });
      }
    };

    // Tab visibility (tab switching = distraction pattern)
    const onVisibility = () => {
      if (document.hidden) {
        this.cognitiveEvents.push({ timestamp: Date.now(), type: "tab_switch" });
      }
    };

    // Form submit
    const onSubmit = (e: Event) => {
      this.cognitiveEvents.push({ timestamp: Date.now(), type: "submit", context: e.isTrusted ? "user" : "script" });
    };

    // Orientation change
    const onOrientation = () => {
      this.cognitiveEvents.push({ timestamp: Date.now(), type: "idle_end", context: "orientation_change" });
    };

    // Selection change
    const onSelection = () => {
      this.cognitiveEvents.push({ timestamp: Date.now(), type: "selection_change" });
    };

    // Hesitation & Pre-submit pause
    const onMouseDownSubmit = (e: globalThis.MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target?.tagName === "BUTTON" || (target as HTMLInputElement)?.type === "submit") {
        if (this.lastKeyUpTime) {
          const pause = Date.now() - this.lastKeyUpTime;
          this.cognitiveEvents.push({
            timestamp: Date.now(), type: "pre_submit_pause", duration_ms: pause,
          });
        }
      }
    };

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

    document.addEventListener("paste", onPasteCut as EventListener, { passive: true });
    document.addEventListener("cut", onPasteCut as EventListener, { passive: true });
    document.addEventListener("input", onInput, { passive: true, capture: true });
    document.addEventListener("visibilitychange", onVisibility, { passive: true });
    document.addEventListener("submit", onSubmit, { passive: true });
    document.addEventListener("selectionchange", onSelection, { passive: true });
    window.addEventListener("orientationchange", onOrientation, { passive: true });
    document.addEventListener("mouseenter", onMouseEnterSubmit, { passive: true, capture: true });
    document.addEventListener("mousedown", onMouseDownSubmit, { passive: true, capture: true });

    this.cleanupFns.push(() => {
      document.removeEventListener("paste", onPasteCut as EventListener);
      document.removeEventListener("cut", onPasteCut as EventListener);
      document.removeEventListener("input", onInput, { capture: true });
      document.removeEventListener("visibilitychange", onVisibility);
      document.removeEventListener("submit", onSubmit);
      document.removeEventListener("selectionchange", onSelection);
      window.removeEventListener("orientationchange", onOrientation);
      document.removeEventListener("mouseenter", onMouseEnterSubmit, { capture: true });
      document.removeEventListener("mousedown", onMouseDownSubmit, { capture: true });
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
    const touchMoves = this.touchEvents.filter(t => t.type === "move");
    for (let i = 1; i < touchMoves.length; i++) {
      const prev = touchMoves[i - 1];
      const curr = touchMoves[i];
      const dt = curr.timestamp - prev.timestamp;
      if (dt > 0 && dt < 1000) {
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
    const scrollReversalRate = this.scrollEvents.length > 1 ? reversals / (this.scrollEvents.length - 1) : 0;

    // Navigation
    const dwells = this.navigationEvents.map((n) => n.dwell_ms);
    const fieldRevisits = this.cognitiveEvents.filter((c) => c.type === "field_revisit").length;
    const strippedFocusSeq = this.focusSequence.map(s => s.replace(/[0-9:]+/g, ""));

    // Cognitive
    const hesitations = this.cognitiveEvents.filter((c) => c.type === "hesitation");
    const hesitationDurations = hesitations.map((h) => h.duration_ms ?? 0);
    const correctionRate = this.totalKeystrokes > 0 ? this.backspaceCount / this.totalKeystrokes : 0;

    // Digraph (Bigram) per-pair tracking
    const digraphStats: Record<string, number[]> = {};
    for (let i = 1; i < this.keystrokeEvents.length; i++) {
      const prev = this.keystrokeEvents[i - 1];
      const curr = this.keystrokeEvents[i];
      if (prev.key.length === 1 && curr.key.length === 1 && curr.flight_time > 0 && curr.flight_time < 500) {
        const pair = `${prev.key.toLowerCase()}${curr.key.toLowerCase()}`;
        if (!digraphStats[pair]) digraphStats[pair] = [];
        digraphStats[pair].push(curr.flight_time);
      }
    }
    const topDigraphs = Object.entries(digraphStats)
      .sort((a, b) => b[1].length - a[1].length)
      .slice(0, 5);
    const digraphFeatures: Record<string, number> = {};
    for (const [pair, times] of topDigraphs) {
      digraphFeatures[`digraph_${pair}_mean`] = mean(times);
      digraphFeatures[`digraph_${pair}_std`] = std(times);
    }

    // Data Familiarity Signal
    const sensitiveSpeeds: number[] = [];
    const normalSpeeds: number[] = [];
    for (const evt of this.keystrokeEvents) {
      if (evt.flight_time <= 0) continue;
      const fid = (evt.target_id || "").toLowerCase();
      // Expanded explicit list of fields matching actual form field IDs
      const isSensitive = fid.includes('account') || fid.includes('beneficiary') || fid.includes('acct') || 
                          fid.includes('amount') || fid.includes('recipient') || fid.includes('routing') ||
                          fid.includes('username') || fid.includes('email');
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
      const ratio = normalMean / sensitiveMean; // Fast sensitive speeds = high familiarity
      if (ratio > 1.2) {
        dataFamiliaritySignal = Math.min(1.0, (ratio - 1.2));
      }
    }

    // Inter-session baseline comparison
    let interSessionDelta = 0;
    if (typeof sessionStorage !== "undefined") {
      const prevMean = parseFloat(sessionStorage.getItem("bca_prev_flight_mean") || "0");
      if (prevMean > 0) {
        const currentMean = mean(this.keystrokeEvents.map(e => e.flight_time).filter(f => f > 0));
        if (currentMean > 0) {
          interSessionDelta = Math.abs(currentMean - prevMean) / prevMean;
        }
      }
    }

    // Mouse trajectory curvature and acceleration
    let trajectoryCurvature = 0;
    const mouseAccs: number[] = [];
    const moveEvents = this.mouseEvents.filter(m => m.type === "move");
    if (moveEvents.length > 5) {
      // Curvature per movement segment (separated by >500ms gaps or clicks)
      let segmentStraight = 0;
      let segmentActual = 0;
      let segmentStart = moveEvents[0];
      
      for (let i = 1; i < moveEvents.length; i++) {
        const prev = moveEvents[i - 1];
        const curr = moveEvents[i];
        const dt = curr.timestamp - prev.timestamp;
        
        // Acceleration
        if (dt > 0 && curr.velocity !== undefined && prev.velocity !== undefined) {
          mouseAccs.push(Math.abs(curr.velocity - prev.velocity) / dt);
        }

        const dist = Math.sqrt((curr.x - prev.x) ** 2 + (curr.y - prev.y) ** 2);
        if (dt > 500) {
          // Finish segment
          const st = Math.sqrt((prev.x - segmentStart.x)**2 + (prev.y - segmentStart.y)**2);
          segmentStraight += st;
          segmentStart = curr;
        } else {
          segmentActual += dist;
        }
      }
      const st = Math.sqrt((moveEvents[moveEvents.length-1].x - segmentStart.x)**2 + (moveEvents[moveEvents.length-1].y - segmentStart.y)**2);
      segmentStraight += st;
      trajectoryCurvature = segmentStraight > 0 ? (segmentActual / segmentStraight) - 1 : 0;
    }

    // Idle ratio & Rapid Submit
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
    
    // Rapid submit logic fixed: time between first keystroke and submit
    const submitEvt = this.cognitiveEvents.find(c => c.type === "submit");
    const rapidSubmit = (this._firstKeystrokeTime > 0 && submitEvt && (submitEvt.timestamp - (this.sessionStart + this._firstKeystrokeTime)) < 3000 && this.totalKeystrokes > 5) ? 1 : 0;

    // Flight times CoV
    const flights = this.keystrokeEvents.map(e => e.flight_time).filter(f => f > 0);
    const flightCv = mean(flights) > 0 ? std(flights) / mean(flights) : 0;

    // Micro vibrations (mobile)
    let microVibes = 0;
    if (this.motionEvents.length > 0 && this.keystrokeEvents.length > 0) {
      // Just approximate by looking at std of acc during keystrokes
      microVibes = std(this.motionEvents.slice(-50).map(m => m.acc_x + m.acc_y + m.acc_z));
    }

    const preSubmitPauses = this.cognitiveEvents.filter(c => c.type === "pre_submit_pause").map(c => c.duration_ms || 0);

    const accMagnitudes = this.motionEvents.map(m => Math.sqrt((m.acc_x||0)**2 + (m.acc_y||0)**2 + (m.acc_z||0)**2));
    const rotMagnitudes = this.motionEvents.filter(m => m.rot_alpha !== undefined).map(m => Math.sqrt((m.rot_alpha||0)**2 + (m.rot_beta||0)**2 + (m.rot_gamma||0)**2));

    // ── Phase 2: Enhanced behavioral signal computation ─────────────────

    // Typing Rhythm Entropy: quantize hold times into 8 bins, compute Shannon entropy
    const holdTimes = this.keystrokeEvents.map(e => e.hold_time).filter(h => h > 0 && h < 2000);
    let typingRhythmEntropy = 0;
    if (holdTimes.length > 5) {
      const minH = Math.min(...holdTimes);
      const maxH = Math.max(...holdTimes);
      const range = maxH - minH || 1;
      const bins = new Array(8).fill(0);
      for (const h of holdTimes) {
        const bin = Math.min(7, Math.floor(((h - minH) / range) * 8));
        bins[bin]++;
      }
      typingRhythmEntropy = bins.filter(b => b > 0).reduce((ent, b) => {
        const p = b / holdTimes.length;
        return ent - p * Math.log2(p);
      }, 0);
    }

    // Typing Burst Detection: consecutive keys with flight_time < 80ms
    let burstCount = 0;
    let burstKeys = 0;
    let currentBurstLen = 1;
    for (let i = 1; i < this.keystrokeEvents.length; i++) {
      if (this.keystrokeEvents[i].flight_time > 0 && this.keystrokeEvents[i].flight_time < 80) {
        currentBurstLen++;
      } else {
        if (currentBurstLen >= 3) { // 3+ rapid keys = a burst
          burstCount++;
          burstKeys += currentBurstLen;
        }
        currentBurstLen = 1;
      }
    }
    if (currentBurstLen >= 3) { burstCount++; burstKeys += currentBurstLen; }
    const burstMeanLength = burstCount > 0 ? burstKeys / burstCount : 0;
    const burstRatio = this.totalKeystrokes > 0 ? burstKeys / this.totalKeystrokes : 0;

    // Mouse Click Intervals & Double-Click Detection
    const clickEvents = this.mouseEvents.filter(m => m.type === "click");
    const clickIntervals: number[] = [];
    let dblClickCount = 0;
    for (let i = 1; i < clickEvents.length; i++) {
      const interval = clickEvents[i].timestamp - clickEvents[i - 1].timestamp;
      if (interval > 0 && interval < 10000) {
        clickIntervals.push(interval);
        if (interval < 350) dblClickCount++;
      }
    }

    // Hover Dwell Tracking (from navigation events on interactive elements)
    const hoverDwells = this.navigationEvents
      .filter(n => n.dwell_ms > 200 && n.dwell_ms < 30000) // 200ms–30s = meaningful hover
      .map(n => n.dwell_ms);

    // Keystroke Pressure Variance (for touch devices)
    const pressures = this.keystrokeEvents
      .map(e => e.pressure || 0)
      .filter(p => p > 0);
    const pressureVariance = pressures.length > 2 ? std(pressures) ** 2 : 0;

    // Mouse Path Straightness per Segment
    const segments: { straight: number; actual: number }[] = [];
    let segStart = moveEvents[0];
    let segActual = 0;
    for (let i = 1; i < moveEvents.length; i++) {
      const prev = moveEvents[i - 1];
      const curr = moveEvents[i];
      const dt = curr.timestamp - prev.timestamp;
      const dist = Math.sqrt((curr.x - prev.x) ** 2 + (curr.y - prev.y) ** 2);
      if (dt > 500 || i === moveEvents.length - 1) {
        const st = Math.sqrt((curr.x - (segStart?.x || 0)) ** 2 + (curr.y - (segStart?.y || 0)) ** 2);
        if (segActual > 0) {
          segments.push({ straight: st, actual: segActual });
        }
        segStart = curr;
        segActual = 0;
      } else {
        segActual += dist;
      }
    }
    const straightnessRatios = segments
      .filter(s => s.actual > 0)
      .map(s => Math.min(1, s.straight / s.actual));
    const mousePathStraightness = mean(straightnessRatios);

    // Scroll Reading WPM (estimate: average ~250 words per viewport height, scale by scroll speed)
    const avgScrollVel = mean(scrollVels.filter(v => v > 0 && v < 10)); // px/ms, reasonable range
    const scrollReadingWpm = avgScrollVel > 0
      ? Math.min(1200, Math.round(avgScrollVel * 60000 / (typeof window !== "undefined" ? window.innerHeight : 800) * 250))
      : 0;

    // Mouse Direction Histogram (8 bins for cardinal + inter-cardinal)
    const dirBins = new Array(8).fill(0);
    for (let i = 1; i < moveEvents.length; i++) {
      const dx = moveEvents[i].x - moveEvents[i - 1].x;
      const dy = moveEvents[i].y - moveEvents[i - 1].y;
      if (Math.abs(dx) + Math.abs(dy) < 0.001) continue; // skip stationary
      let angle = Math.atan2(dy, dx) * (180 / Math.PI);
      if (angle < 0) angle += 360;
      const bin = Math.min(7, Math.floor(angle / 45));
      dirBins[bin]++;
    }
    const dirTotal = dirBins.reduce((a: number, b: number) => a + b, 0);
    const mouseDirEntropy = dirTotal > 0
      ? dirBins.filter((b: number) => b > 0).reduce((ent: number, b: number) => {
          const p = b / dirTotal;
          return ent - p * Math.log2(p);
        }, 0)
      : 0;

    // Keystroke Rhythm Consistency (1 - CoV of hold times)
    const holdCov = mean(holdTimes) > 0 ? std(holdTimes) / mean(holdTimes) : 1;
    const keystrokeRhythmConsistency = Math.max(0, Math.min(1, 1 - holdCov));

    // Typing Speed WPM
    const typingSpeedWpm = this.totalKeystrokes > 5 && sessionDuration > 1000
      ? Math.round((this.totalKeystrokes / 5) / (sessionDuration / 60000))
      : 0;

    return {
      ...digraphFeatures,
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
      nav_focus_sequence_entropy: strippedFocusSeq.length > 0 ? shannonEntropy(strippedFocusSeq) : 0,
      // Cognitive
      hesitation_count: hesitations.length,
      hesitation_duration_mean: mean(hesitationDurations),
      correction_rate: correctionRate,
      copy_paste_count: this.cognitiveEvents.filter((c) => c.type === "copy_paste" || c.type === "autofill").length,
      reread_count: this.cognitiveEvents.filter((c) => c.type === "reread").length,
      tab_switch_count: this.cognitiveEvents.filter((c) => c.type === "tab_switch").length,
      rapid_submit_detected: rapidSubmit,
      data_familiarity_signal: dataFamiliaritySignal,
      typing_hold_variance: std(this.keystrokeEvents.map(e => e.hold_time)),
      pre_submit_pause_mean: mean(preSubmitPauses),
      trajectory_curvature: Math.max(0, trajectoryCurvature),
      inter_session_speed_delta: interSessionDelta,
      flight_time_cv: flightCv,
      bigram_speed_mean: mean(flights),
      // Motion
      motion_acc_mean: mean(accMagnitudes),
      motion_acc_std: std(accMagnitudes),
      motion_rotation_mean: mean(rotMagnitudes),
      motion_event_count: this.motionEvents.length,
      micro_vibration_mean: microVibes,
      // Session
      total_active_ms: activeMs,
      idle_ratio: Math.min(1, Math.max(0, idleRatio)),
      mouse_acceleration_mean: mean(mouseAccs),
      total_keystrokes: this.totalKeystrokes,
      modifier_overlap_mean: mean(this.modifierOverlaps),
      modifier_overlap_std: std(this.modifierOverlaps),
      modifier_overlap_count: this.modifierOverlaps.length,
      // ── Phase 2: Enhanced behavioral signals ──────────────────────────
      typing_rhythm_entropy: typingRhythmEntropy,
      typing_burst_count: burstCount,
      typing_burst_mean_length: burstMeanLength,
      typing_burst_ratio: burstRatio,
      mouse_click_interval_mean: mean(clickIntervals),
      mouse_click_interval_std: std(clickIntervals),
      mouse_dblclick_count: dblClickCount,
      hover_dwell_mean: mean(hoverDwells),
      hover_dwell_max: hoverDwells.length > 0 ? Math.max(...hoverDwells) : 0,
      hover_count: hoverDwells.length,
      keystroke_pressure_variance: pressureVariance,
      mouse_path_straightness: mousePathStraightness,
      mouse_path_segment_count: segments.length,
      scroll_reading_wpm: scrollReadingWpm,
      scroll_depth_pct: Math.round(this.maxScrollDepth * 100),
      mouse_dir_histogram_0: dirBins[0],
      mouse_dir_histogram_1: dirBins[1],
      mouse_dir_histogram_2: dirBins[2],
      mouse_dir_histogram_3: dirBins[3],
      mouse_dir_histogram_4: dirBins[4],
      mouse_dir_histogram_5: dirBins[5],
      mouse_dir_histogram_6: dirBins[6],
      mouse_dir_histogram_7: dirBins[7],
      mouse_dir_entropy: mouseDirEntropy,
      keystroke_rhythm_consistency: keystrokeRhythmConsistency,
      typing_speed_wpm: typingSpeedWpm,
    };
  }

  // ── Payload Builder ───────────────────────────────────────────────────────

  private async _buildPayload(sessionId: string): Promise<ExtendedBehavioralPayload> {
    const now = Date.now();
    
    // Normalize mouse coordinates to 0-1 range to prevent UI reconstruction
    const w = typeof window !== "undefined" ? window.innerWidth : 1000;
    const h = typeof window !== "undefined" ? window.innerHeight : 1000;
    const safeMouseEvents = this.mouseEvents.map(m => ({
      ...m,
      x: m.x / w,
      y: m.y / h
    }));

    // Sequence integrity hash (SHA-256)
    const timestamps = [
      ...this.keystrokeEvents.map(e => e.timestamp),
      ...this.mouseEvents.map(e => e.timestamp),
      ...this.touchEvents.map(e => e.timestamp)
    ].sort((a, b) => a - b);
    
    const tsString = timestamps.join(",");
    let sequence_hash = "0";
    if (typeof crypto !== "undefined" && crypto.subtle) {
      const msgBuffer = new TextEncoder().encode(tsString);
      const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      sequence_hash = hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
    }

    // Clock skew detection
    const expectedNow = this._loadDateNow + performance.now() - this._sdkLoadTime;
    const clock_skew = Math.abs(now - expectedNow);

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
      mouse_events: safeMouseEvents,
      touch_events: [...this.touchEvents],
      scroll_events: [...this.scrollEvents],
      navigation_events: [...this.navigationEvents],
      motion_events: [...this.motionEvents],
      cognitive_events: [...this.cognitiveEvents],
      extended_features: this.computeExtendedFeatures(),
      sequence_hash,
      clock_skew
    };
  }

  // ── Snapshot & Flush ──────────────────────────────────────────────────────

  async flush(sessionId: string): Promise<ExtendedBehavioralPayload> {
    const payload = await this._buildPayload(sessionId);

    // Save inter-session mean
    if (this.keystrokeEvents.length > 5) {
      const flights = this.keystrokeEvents.filter(e => e.flight_time > 0).map(e => e.flight_time);
      if (flights.length > 0) {
        const meanFlight = flights.reduce((a, b) => a + b, 0) / flights.length;
        if (typeof sessionStorage !== "undefined") {
          sessionStorage.setItem("bca_prev_flight_mean", meanFlight.toString());
        }
      }
    }

    // Clear buffers after flush (keep session-level counters)
    this.keystrokeEvents.length = 0;
    this.mouseEvents.length = 0;
    this.touchEvents.length = 0;
    this.scrollEvents.length = 0;
    this.navigationEvents.length = 0;
    this.motionEvents.length = 0;
    // Keep cognitive events for session-level analysis

    return payload;
  }

  /** Quick snapshot without clearing buffers - useful for calibration */
  async snapshot(sessionId: string): Promise<ExtendedBehavioralPayload> {
    return await this._buildPayload(sessionId);
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

export function resetCollectorForTesting() {
  if (_collector) {
    _collector.stop();
    _collector = null;
  }
}

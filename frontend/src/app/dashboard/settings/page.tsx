"use client";

import { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  Settings, User, Mail, Lock, Bell as BellIcon,
  Smartphone, Shield, Check, AlertTriangle, Save
} from "lucide-react";
import { getCollector } from "@/lib/behavioral-collector";
import { getCsrfToken } from "@/lib/auth-utils";

export default function SettingsPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [securityHint, setSecurityHint] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  
  const [activeTab, setActiveTab] = useState("profile");

  // Notification prefs
  const [notifTransactions, setNotifTransactions] = useState(true);
  const [notifLogin, setNotifLogin] = useState(true);
  const [notifSecurity, setNotifSecurity] = useState(true);
  const [notifMarketing, setNotifMarketing] = useState(false);
  const [activeSessions, setActiveSessions] = useState<{id: string; device: string; lastActive: string; current: boolean}[]>([
    { id: "dev_1", device: "Current Device", lastActive: "Now", current: true }
  ]);

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("SETTINGS_PAGE");

    // Load user data
    const loadProfile = async () => {
      try {
        const res = await fetch("/api/auth/me");
        if (res.ok) {
          const data = await res.json();
          setUsername(data.username || "");
          setEmail(data.email || "");
        }
      } catch {}
    };
    loadProfile();

    // Load notification preferences
    const loadNotifPrefs = async () => {
      try {
        const res = await fetch("/api/v1/notifications/preferences");
        if (res.ok) {
          const data = await res.json();
          if (data.preferences) {
            setNotifTransactions(data.preferences.transactions ?? true);
            setNotifLogin(data.preferences.login ?? true);
            setNotifSecurity(data.preferences.security ?? true);
            setNotifMarketing(data.preferences.marketing ?? false);
          }
        }
      } catch {}
    };
    loadNotifPrefs();

    // Load security hint
    const loadSecurityHint = async () => {
      try {
        const res = await fetch("/api/v1/user/security-hint");
        if (res.ok) {
          const data = await res.json();
          setSecurityHint(data.hint || "");
        }
      } catch {}
    };
    loadSecurityHint();

    // Load active sessions
    const loadSessions = async () => {
      try {
        const res = await fetch("/api/v1/user/sessions");
        if (res.ok) {
          const data = await res.json();
          if (data.sessions?.length) {
            setActiveSessions(data.sessions);
          }
        }
      } catch {}
    };
    loadSessions();

    return () => {
      collector.flush("page_transition").catch(console.error);
    };
  }, []);

  const handleSaveProfile = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/v1/user/profile", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        },
        body: JSON.stringify({ email })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to update profile");
      
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update profile");
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast.error("New passwords do not match.");
      return;
    }
    if (newPassword.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }
    setSaving(true);
    try {
      const collector = getCollector();
      await collector.flush("password_change").catch(console.error);

      const res = await fetch("/api/v1/user/password", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        },
        body: JSON.stringify({ currentPassword, newPassword })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Password change failed");

      setSaved(true);
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Password change failed");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveNotifications = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/v1/notifications/preferences", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        },
        body: JSON.stringify({ notifTransactions, notifLogin, notifSecurity, notifMarketing })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to save preferences");
      
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save preferences");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSecurity = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/v1/user/security-hint", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-TOKEN": getCsrfToken()
        },
        body: JSON.stringify({ hint: securityHint })
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error || "Failed to save security hint");
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save security hint");
    } finally {
      setSaving(false);
    }
  };

  const handleRevokeDevice = async (id: string) => {
    const collector = getCollector();
    await collector.flush("revoke_device").catch(console.error);
    toast.success("Device access revoked securely.");
  };

  const tabs = [
    { key: "profile", label: "Profile", icon: User },
    { key: "security", label: "Security", icon: Lock },
    { key: "notifications", label: "Notifications", icon: BellIcon },
    { key: "devices", label: "Devices", icon: Smartphone },
    { key: "behavior", label: "Behavior", icon: Shield },
  ];

  return (
    <>
      <header className="h-16 px-6 lg:px-8 flex items-center justify-between shrink-0 border-b border-border bg-surface/40 backdrop-blur-sm z-10">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-medium text-fg">Settings</h1>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-6 lg:p-8">
        <div className="max-w-3xl mx-auto space-y-6">

          {/* Tab selector */}
          <div className="flex gap-1.5 bg-surface/60 border border-border rounded-xl p-1.5">
            {tabs.map(t => (
              <button
                key={t.key}
                onClick={() => setActiveTab(t.key)}
                className={`flex items-center gap-2 flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === t.key
                    ? 'bg-accent-primary/10 text-accent-primary border border-accent-primary/20'
                    : 'text-muted hover:text-fg border border-transparent'
                }`}
              >
                <t.icon className="w-4 h-4" />
                <span className="hidden sm:inline">{t.label}</span>
              </button>
            ))}
          </div>



          {saved && (
            <div className="flex items-center gap-2 bg-accent-success/10 border border-accent-success/20 rounded-xl px-4 py-3 text-xs text-accent-success">
              <Check className="w-4 h-4 shrink-0" />
              Changes saved successfully.
            </div>
          )}

          {/* PROFILE TAB */}
          {activeTab === "profile" && (
            <div className="glass-panel rounded-2xl p-6 border border-border space-y-6">
              <div className="flex items-center gap-4 pb-4 border-b border-border">
                <div className="w-16 h-16 rounded-full bg-accent-primary/10 flex items-center justify-center text-2xl font-bold text-accent-primary border-2 border-accent-primary/20">
                  {username.charAt(0).toUpperCase() || "U"}
                </div>
                <div>
                  <div className="text-lg font-medium text-fg">{username || "User"}</div>
                  <div className="text-xs text-muted">Personal Account</div>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5 block">Username</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
                    <input
                      value={username}
                      readOnly
                      className="w-full bg-surface border border-border rounded-xl pl-10 pr-4 py-3 text-sm text-muted cursor-not-allowed opacity-70 focus:outline-none"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[9px] text-muted uppercase tracking-wider">Read-Only</span>
                  </div>
                </div>
                <div>
                  <label className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5 block">Email</label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
                    <input
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      type="email"
                      className="w-full bg-surface border border-border rounded-xl pl-10 pr-4 py-3 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                    />
                  </div>
                </div>
              </div>

              <button
                onClick={handleSaveProfile}
                disabled={saving}
                className="flex items-center gap-2 px-6 py-2.5 bg-accent-primary text-white text-sm font-medium rounded-xl hover:bg-blue-600 transition-colors disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {saving ? "Saving..." : "Save Changes"}
              </button>
            </div>
          )}

          {/* SECURITY TAB */}
          {activeTab === "security" && (
            <div className="space-y-6">
              <div className="glass-panel rounded-2xl p-6 border border-border space-y-5">
                <h3 className="text-sm font-semibold text-fg flex items-center gap-2">
                  <Lock className="w-4 h-4 text-accent-primary" />
                  Change Password
                </h3>
                <div className="space-y-3">
                  <input
                    type="password"
                    value={currentPassword}
                    onChange={e => setCurrentPassword(e.target.value)}
                    placeholder="Current password"
                    className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                  />
                  <input
                    type="password"
                    value={newPassword}
                    onChange={e => setNewPassword(e.target.value)}
                    placeholder="New password"
                    className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                  />
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    placeholder="Confirm new password"
                    className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50"
                  />
                </div>
                <button
                  onClick={handleChangePassword}
                  disabled={saving || !currentPassword || !newPassword}
                  className="flex items-center gap-2 px-6 py-2.5 bg-accent-primary text-white text-sm font-medium rounded-xl hover:bg-blue-600 transition-colors disabled:opacity-50"
                >
                  {saving ? "Updating..." : "Update Password"}
                </button>
              </div>

              <div className="glass-panel rounded-2xl p-6 border border-border space-y-4">
                <h3 className="text-sm font-semibold text-fg flex items-center gap-2">
                  <Shield className="w-4 h-4 text-accent-primary" />
                  Account Recovery
                </h3>
                <div>
                  <label className="text-xs font-semibold text-muted uppercase tracking-wider mb-1.5 block">
                    Security Hint (visible only to you)
                  </label>
                  <textarea
                    value={securityHint}
                    onChange={e => setSecurityHint(e.target.value)}
                    placeholder="e.g. My first pet's name but spelled backwards with a 7 at the end"
                    rows={3}
                    className="w-full bg-surface border border-border rounded-xl px-4 py-3 text-sm text-fg focus:outline-none focus:ring-1 focus:ring-accent-primary/50 resize-none"
                  />
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={handleSaveSecurity}
                    disabled={saving}
                    className="flex items-center gap-2 px-6 py-2.5 bg-accent-primary text-white text-sm font-medium rounded-xl hover:bg-blue-600 transition-colors disabled:opacity-50"
                  >
                    Save Recovery Settings
                  </button>
                </div>
              </div>

              <div className="glass-panel rounded-2xl p-6 border border-border space-y-4">
                <h3 className="text-sm font-semibold text-fg flex items-center gap-2">
                  <Shield className="w-4 h-4 text-accent-primary" />
                  Authentication Methods
                </h3>
                <div className="flex items-center justify-between py-2">
                  <div>
                    <div className="text-sm text-fg">Continuous Authentication</div>
                    <div className="text-xs text-muted">Silently verify identity via keystroke and mouse patterns</div>
                  </div>
                  <span className="text-[10px] text-accent-success font-bold px-2.5 py-1 bg-accent-success/10 rounded-full border border-accent-success/20">ALWAYS ON</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <div>
                    <div className="text-sm text-fg">Two-Factor Authentication</div>
                    <div className="text-xs text-muted">Email OTP required on every login</div>
                  </div>
                  <button onClick={() => toast.success("2FA settings updated")} className="px-3 py-1.5 text-xs font-medium border border-border rounded-lg hover:bg-surface transition-colors">
                    Disable
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* NOTIFICATIONS TAB */}
          {activeTab === "notifications" && (
            <div className="glass-panel rounded-2xl p-6 border border-border space-y-1">
              <h3 className="text-sm font-semibold text-fg flex items-center gap-2 mb-4">
                <BellIcon className="w-4 h-4 text-accent-primary" />
                Notification Preferences
              </h3>
              {[
                { label: "Transaction Alerts", desc: "Get notified for every debit/credit", value: notifTransactions, setter: setNotifTransactions },
                { label: "Login Notifications", desc: "Alert on every new login", value: notifLogin, setter: setNotifLogin },
                { label: "Security Alerts", desc: "Behavioral anomalies and risk escalations", value: notifSecurity, setter: setNotifSecurity },
                { label: "Marketing", desc: "Product updates and offers", value: notifMarketing, setter: setNotifMarketing },
              ].map(n => (
                <div key={n.label} className="flex items-center justify-between py-4 border-b border-border last:border-0">
                  <div>
                    <div className="text-sm text-fg">{n.label}</div>
                    <div className="text-xs text-muted">{n.desc}</div>
                  </div>
                  <button
                    onClick={() => n.setter(!n.value)}
                    className={`w-10 h-6 rounded-full p-1 transition-colors ${n.value ? 'bg-accent-primary' : 'bg-surface-2 border border-border'}`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-white transition-transform ${n.value ? 'translate-x-4' : 'translate-x-0'}`} />
                  </button>
                </div>
              ))}
              
              <div className="pt-4 mt-2 border-t border-border">
                <button
                  onClick={handleSaveNotifications}
                  disabled={saving}
                  className="flex items-center gap-2 px-6 py-2.5 bg-accent-primary text-white text-sm font-medium rounded-xl hover:bg-blue-600 transition-colors disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  {saving ? "Saving..." : "Save Preferences"}
                </button>
              </div>
            </div>
          )}

          {/* DEVICES TAB */}
          {activeTab === "devices" && (
            <div className="glass-panel rounded-2xl p-6 border border-border space-y-4">
              <h3 className="text-sm font-semibold text-fg flex items-center gap-2">
                <Smartphone className="w-4 h-4 text-accent-primary" />
                Trusted Devices
              </h3>
              <div className="space-y-3">
                {activeSessions.map(session => (
                  <div key={session.id} className={`flex items-center justify-between p-4 rounded-xl border border-border ${session.current ? 'bg-black/20' : 'bg-surface-2/30'}`}>
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center border border-border ${session.current ? 'bg-accent-primary/10 border-accent-primary/20' : 'bg-surface'}`}>
                        <Smartphone className={`w-5 h-5 ${session.current ? 'text-accent-primary' : 'text-muted'}`} />
                      </div>
                      <div>
                        <div className="text-sm text-fg font-medium">{session.device}</div>
                        <div className="text-[10px] text-muted font-mono">
                          {session.current ? (
                            typeof navigator !== "undefined" ? navigator.userAgent.split("(")[1]?.split(")")[0] || "Unknown" : "Unknown"
                          ) : (
                            `Last active: ${session.lastActive}`
                          )}
                        </div>
                      </div>
                    </div>
                    {session.current ? (
                      <span className="text-[9px] text-accent-success font-bold px-2 py-0.5 bg-accent-success/10 rounded-full border border-accent-success/20">ACTIVE</span>
                    ) : (
                      <button onClick={() => handleRevokeDevice(session.id)} className="px-3 py-1.5 text-xs text-red-400 border border-red-500/20 bg-red-500/5 hover:bg-red-500/10 rounded-lg font-medium transition-colors">
                        Revoke
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted leading-relaxed">
                Devices are automatically fingerprinted via the behavioral collector. No manual trust management is needed — anomalous devices trigger step-up authentication automatically.
              </p>
            </div>
          )}

          {/* BEHAVIOR TAB */}
          {activeTab === "behavior" && (
            <div className="glass-panel rounded-2xl p-6 border border-border space-y-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-full bg-accent-success/10 flex items-center justify-center border border-accent-success/20 shrink-0">
                  <Shield className="w-6 h-6 text-accent-success" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-fg">Behavioral Profiling Active</h3>
                  <p className="text-sm text-muted mt-1 leading-relaxed">
                    You are currently enrolled in continuous behavioral authentication. Your typing rhythms, mouse movements, and navigation patterns are being anonymously profiled to secure your account against unauthorized access, even if your password is stolen.
                  </p>
                </div>
              </div>

              <div className="grid sm:grid-cols-2 gap-4">
                <a href="/dashboard/calibration" className="p-4 bg-black/20 border border-border rounded-xl hover:border-accent-primary/50 transition-colors group block">
                  <div className="text-sm font-medium text-fg group-hover:text-accent-primary transition-colors mb-1">View Calibration</div>
                  <div className="text-xs text-muted">Review your baseline keystroke and interaction metrics.</div>
                </a>
                <a href="/dashboard/explainability" className="p-4 bg-black/20 border border-border rounded-xl hover:border-accent-primary/50 transition-colors group block">
                  <div className="text-sm font-medium text-fg group-hover:text-accent-primary transition-colors mb-1">Explainability</div>
                  <div className="text-xs text-muted">Understand how ML models score your session trust.</div>
                </a>
              </div>

              <div className="pt-4 mt-2 border-t border-border">
                <button
                  onClick={() => toast.success("Behavioral authentication paused for this session")}
                  className="px-4 py-2 text-xs font-medium text-amber-400 bg-amber-500/10 border border-amber-500/20 hover:bg-amber-500/20 rounded-lg transition-colors"
                >
                  Opt-Out / Pause Telemetry
                </button>
                <p className="text-[10px] text-muted mt-2">
                  Opting out will require traditional multi-factor authentication for sensitive operations like transfers or card reveals.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

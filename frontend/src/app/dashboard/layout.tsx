"use client";

import { useState, useEffect, Suspense } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import {
  LayoutGrid, ArrowLeftRight, CreditCard, PieChart, FileText,
  Settings, LogOut, Menu, X, Shield, Activity, Fingerprint, Brain
} from "lucide-react";
import { TelemetryProvider, useTelemetry } from "@/components/TelemetryProvider";

const navItems = [
  { href: "/dashboard", label: "Overview", icon: LayoutGrid },
  { href: "/dashboard/transfers", label: "Transfers", icon: ArrowLeftRight },
  { href: "/dashboard/cards", label: "Cards", icon: CreditCard },
  { href: "/dashboard/investments", label: "Investments", icon: PieChart },
  { href: "/dashboard/statements", label: "Statements", icon: FileText },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

const SidebarItem = ({ icon: Icon, label, active, href }: { icon: any; label: string; active?: boolean; href: string }) => (
  <Link href={href} className="no-underline">
    <div className={`flex items-center gap-3 px-3 py-2 text-sm rounded-md cursor-pointer transition-colors ${active ? 'bg-surface-2 text-fg font-medium' : 'text-muted hover:text-fg hover:bg-surface-2'}`}>
      <Icon className="w-4 h-4" />
      {label}
    </div>
  </Link>
);

const GlobalTrustWidget = () => {
  const { score, enrollment } = useTelemetry();
  return (
    <div className="mx-4 mb-4 mt-2 p-3 bg-black/40 border border-border rounded-xl">
      <div className="flex items-center gap-2 mb-2">
        <Activity className="w-3.5 h-3.5 text-accent-success" />
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">Continuous Auth</span>
      </div>
      <div className="flex items-end justify-between">
        <span className="text-xl font-medium tracking-tighter tabular-nums text-fg">
          {score !== null ? `${score}%` : <div className="h-6 w-12 bg-black/20 animate-pulse rounded"></div>}
        </span>
        <span className="text-[10px] text-muted">
          {enrollment && !enrollment.enrolled ? `Learning (${Math.round((enrollment.completed/enrollment.required)*100)}%)` : 'Secured'}
        </span>
      </div>
      <div className="mt-2 h-1 w-full bg-black/40 rounded-full overflow-hidden">
        <div 
          className={`h-full ${score !== null && score > 75 ? 'bg-accent-success' : 'bg-accent-danger'} transition-all duration-500`}
          style={{ width: `${score || 0}%` }}
        />
      </div>
    </div>
  );
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [username, setUsername] = useState("User");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const res = await fetch("/api/auth/me");
        if (!res.ok) { router.push("/login"); return; }
        const data = await res.json();
        setUsername(data.username || "User");
      } catch {
        router.push("/login");
      }
    };
    checkAuth();
  }, [router]);

  // Close mobile sidebar on route change
  useEffect(() => { setMobileOpen(false); }, [pathname]);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } catch {} finally {
      router.push("/login");
    }
  };

  const sidebarContent = (
    <>
      {/* Logo */}
      <div className="h-16 px-6 flex items-center gap-3 border-b border-border shrink-0">
        <div className="w-8 h-8 bg-accent-primary/20 rounded-lg flex items-center justify-center border border-accent-primary/30">
          <Shield className="w-4 h-4 text-accent-primary" />
        </div>
        <span className="font-semibold tracking-tight text-lg">AetherAuth</span>
      </div>

      {/* Navigation */}
      <div className="p-4 flex flex-col gap-1 flex-1 overflow-y-auto">
        <div className="text-[10px] uppercase tracking-wider text-muted font-bold mb-2 px-3 mt-2">Menu</div>
        {navItems.map(item => (
          <SidebarItem
            key={item.href}
            icon={item.icon}
            label={item.label}
            active={pathname === item.href}
            href={item.href}
          />
        ))}
        <div className="text-[10px] uppercase tracking-wider text-muted font-bold mb-2 px-3 mt-4">Biometrics</div>
        <SidebarItem icon={Fingerprint} label="Calibration" active={pathname === "/dashboard/calibration"} href="/dashboard/calibration" />
        <SidebarItem icon={Brain} label="Explainability" active={pathname === "/dashboard/explainability"} href="/dashboard/explainability" />
      </div>
      
      <GlobalTrustWidget />

      {/* User footer with logout */}
      <div className="border-t border-border p-3 space-y-2 shrink-0">
        <div className="flex items-center gap-3 px-2 py-2">
          <div className="w-9 h-9 rounded-full bg-black/40 flex items-center justify-center font-medium text-xs border border-border shrink-0">
            {username.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="text-sm font-medium text-fg truncate">{username}</div>
            <div className="text-xs text-muted">Personal Account</div>
          </div>
        </div>
        <button
          onClick={handleLogout}
          disabled={loggingOut}
          className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 rounded-md transition-colors disabled:opacity-50"
        >
          <LogOut className="w-4 h-4" />
          {loggingOut ? "Signing out..." : "Sign Out"}
        </button>
      </div>
    </>
  );

  return (
    <TelemetryProvider>
      <div className="flex h-screen overflow-hidden text-fg font-sans bg-black">
        {/* Mobile overlay */}
        {mobileOpen && (
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}

        {/* Sidebar — desktop */}
        <aside className="hidden lg:flex w-64 bg-surface/80 backdrop-blur-md border-r border-border flex-col shrink-0 z-10">
          {sidebarContent}
        </aside>

        {/* Sidebar — mobile drawer */}
        <aside className={`fixed inset-y-0 left-0 w-72 bg-surface backdrop-blur-md border-r border-border flex flex-col z-50 transform transition-transform duration-200 lg:hidden ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}>
          <button
            onClick={() => setMobileOpen(false)}
            className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full hover:bg-surface-2 text-muted"
          >
            <X className="w-5 h-5" />
          </button>
          {sidebarContent}
        </aside>

        {/* Main workspace */}
        <div className="flex-1 flex flex-col min-w-0 relative z-0">
          {/* Mobile topbar hamburger */}
          <div className="lg:hidden h-14 px-4 flex items-center border-b border-border bg-surface/60 backdrop-blur-sm shrink-0">
            <button onClick={() => setMobileOpen(true)} className="w-9 h-9 flex items-center justify-center rounded-md hover:bg-surface-2 text-muted">
              <Menu className="w-5 h-5" />
            </button>
            <span className="ml-3 font-semibold text-fg text-sm">AetherAuth</span>
          </div>

          {/* Page content */}
          <ErrorBoundary fallbackTitle="Page failed to load">
            <Suspense fallback={
              <div className="flex flex-col items-center justify-center h-64 text-muted">
                <div className="w-8 h-8 rounded-full border-2 border-accent-primary border-t-transparent animate-spin mb-4"></div>
                Loading...
              </div>
            }>
              {children}
            </Suspense>
          </ErrorBoundary>
        </div>
      </div>
    </TelemetryProvider>
  );
}

"use client";
import { getCsrfToken, getSessionId } from "@/lib/auth-utils";


import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Wordmark } from "@/components/Mark";
import { Shield, BarChart3, FileCheck, Lock, Brain, Book, Zap } from "lucide-react";

const navItems = [
  { href: "/demo", label: "Live Demo", icon: <Zap size={16} /> },
  { href: "/dashboard", label: "Dashboard", icon: <BarChart3 size={16} /> },
  { href: "/compliance", label: "Compliance", icon: <FileCheck size={16} /> },
  { href: "/privacy", label: "Privacy", icon: <Lock size={16} /> },
  { href: "/explainability", label: "Explainability", icon: <Brain size={16} /> },
  { href: "/architecture", label: "Architecture", icon: <Book size={16} /> },
];

/**
 * Gap 22: Always-visible behavioral trust indicator in the nav bar.
 * Shield icon changes color (green/amber/red) based on live session risk score.
 */
function TrustIndicator() {
  const [riskScore, setRiskScore] = useState<number | null>(null);

  useEffect(() => {
    let mounted = true;

    const fetchScore = async () => {
      try {
        const csrfToken = getCsrfToken();
        if (!csrfToken) return;

        const res = await fetch("/api/v1/session/metrics", {
          headers: { "X-CSRF-TOKEN": csrfToken },
        });
        if (res.ok && mounted) {
          const data = await res.json();
          setRiskScore(data.risk_score ?? null);
        }
      } catch { /* silently fail */ }
    };

    fetchScore();
    const interval = setInterval(fetchScore, 15_000); // Poll every 15s
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  if (riskScore === null) return null;

  const trustPct = Math.round((1 - riskScore) * 100);
  const color = riskScore < 0.2
    ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/30"
    : riskScore < 0.5
      ? "text-amber-400 bg-amber-500/10 border-amber-500/30"
      : "text-red-400 bg-red-500/10 border-red-500/30";

  const dotColor = riskScore < 0.2
    ? "bg-emerald-400"
    : riskScore < 0.5
      ? "bg-amber-400"
      : "bg-red-400";

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[0.7rem] font-mono font-medium ${color}`}
      title={`Behavioral trust: ${trustPct}% (risk: ${(riskScore * 100).toFixed(0)}%)`}
    >
      <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${dotColor}`} />
      <Shield size={13} />
      <span>{trustPct}%</span>
    </div>
  );
}

export function NavBar() {
  const pathname = usePathname();

  // Only show nav on dashboard pages
  const isDashboardArea = navItems.some((item) => pathname?.startsWith(item.href));
  if (!isDashboardArea) return null;

  return (
    <nav className="flex items-center gap-1 px-4 py-2 border-b border-white/10 bg-slate-950/90 backdrop-blur-md overflow-x-auto">
      <Link href="/" aria-label="AetherAuth home" className="mr-5 shrink-0">
        <Wordmark />
      </Link>

      {navItems.map((item) => {
        const isActive = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[0.8rem] transition-all duration-150 no-underline whitespace-nowrap shrink-0 ${
              isActive 
                ? "font-semibold text-blue-400 bg-blue-500/15 border border-blue-500/20" 
                : "font-normal text-slate-400 hover:text-slate-200 hover:bg-white/5"
            }`}
          >
            {item.icon}
            {item.label}
          </Link>
        );
      })}

      {/* Gap 22: Always-visible trust indicator */}
      <div className="ml-auto shrink-0">
        <TrustIndicator />
      </div>
    </nav>
  );
}

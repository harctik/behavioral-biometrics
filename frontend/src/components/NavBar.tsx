"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Shield, BarChart3, FileCheck, Lock, Brain, Book, Zap } from "lucide-react";

const navItems = [
  { href: "/demo", label: "Live Demo", icon: <Zap size={16} /> },
  { href: "/dashboard", label: "SOC Dashboard", icon: <BarChart3 size={16} /> },
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
        const csrfToken = document.cookie.match(/csrf_access_token=([^;]+)/)?.[1];
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
    ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.7)]"
    : riskScore < 0.5
      ? "bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.7)]"
      : "bg-red-400 shadow-[0_0_6px_rgba(248,113,113,0.7)]";

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
      <Shield size={18} className="text-blue-500 mr-1.5 shrink-0" />
      <span className="font-bold text-[0.85rem] mr-4 text-slate-100 shrink-0">
        BCA
      </span>

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

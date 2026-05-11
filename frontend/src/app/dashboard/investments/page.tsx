"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  LayoutGrid, ArrowLeftRight, CreditCard, PieChart, FileText, Bell
} from "lucide-react";
import { getCollector } from "@/lib/behavioral-collector";

const SidebarItem = ({ icon: Icon, label, active, href }: { icon: any, label: string, active?: boolean, href?: string }) => {
  const content = (
    <div className={`flex items-center gap-3 px-3 py-2 text-sm rounded-md cursor-pointer transition-colors ${active ? 'bg-surface-2 text-fg font-medium' : 'text-muted hover:text-fg hover:bg-surface-2'}`}>
      <Icon className="w-4 h-4" />
      {label}
    </div>
  );
  return href ? <Link href={href} className="no-underline">{content}</Link> : content;
};

export default function InvestmentsPage() {
  const router = useRouter();
  const [username, setUsername] = useState("Alex Johnson");
  
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("INVESTMENTS_PAGE");
    collector.start();

    const checkAuth = async () => {
      try {
        const res = await fetch("/api/auth/me");
        if (!res.ok) {
          router.push("/login");
          return;
        }
        const data = await res.json();
        setUsername(data.username || "Alex Johnson");
      } catch (err) {
        router.push("/login");
      }
    };
    checkAuth();
    
    return () => {
      collector.stop();
    };
  }, [router]);

  return (
    <div className="flex h-full overflow-hidden text-fg font-sans bg-black">
      {/* Sidebar */}
      <aside className="w-64 bg-surface/80 backdrop-blur-md border-r border-border flex flex-col shrink-0 z-10">
        <div className="h-16 px-6 flex items-center gap-3 border-b border-border">
          <div className="w-8 h-8 bg-accent-primary/20 rounded-lg flex items-center justify-center border border-accent-primary/30">
            <div className="w-3 h-3 bg-accent-primary rounded-sm"></div>
          </div>
          <span className="font-semibold tracking-tight text-lg">NexaBank</span>
        </div>
        <div className="p-4 flex flex-col gap-1 flex-1">
          <div className="text-[10px] uppercase tracking-wider text-muted font-bold mb-2 px-3 mt-2">Menu</div>
          <SidebarItem icon={LayoutGrid} label="Overview" href="/dashboard" />
          <SidebarItem icon={ArrowLeftRight} label="Transfers" href="/dashboard/transfers" />
          <SidebarItem icon={CreditCard} label="Cards" href="/dashboard/cards" />
          <SidebarItem icon={PieChart} label="Investments" active href="/dashboard/investments" />
          <SidebarItem icon={FileText} label="Statements" href="/dashboard/statements" />
        </div>
        <div className="p-4 border-t border-border flex items-center gap-3 cursor-pointer hover:bg-surface-2 transition-colors m-2 rounded-xl">
          <div className="w-9 h-9 rounded-full bg-black/40 flex items-center justify-center font-medium text-xs border border-border">
            {username.charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="text-sm font-medium text-fg">{username}</div>
            <div className="text-xs text-muted">Personal Checking</div>
          </div>
        </div>
      </aside>

      {/* Main Workspace */}
      <main className="flex-1 flex flex-col min-w-0 relative z-0">
        {/* Topbar */}
        <header className="h-16 px-8 flex items-center justify-between shrink-0 border-b border-border bg-surface/40 backdrop-blur-sm z-10">
          <div className="flex items-center">
            <h1 className="text-xl font-medium text-fg">Investments</h1>
            <span className="ml-3 px-2.5 py-1 rounded-md bg-accent-primary/10 border border-accent-primary/20 text-[10px] font-mono font-bold text-accent-primary tracking-wider">CONTEXT: INVESTMENTS_PAGE</span>
          </div>
          <div className="flex items-center gap-6 ml-auto">
            <button className="w-9 h-9 rounded-full flex items-center justify-center hover:bg-surface-2 transition-colors border border-transparent hover:border-border">
              <Bell className="w-4 h-4 text-muted" />
            </button>
          </div>
        </header>

        {/* Scrollable Content */}
        <div className="flex-1 overflow-auto p-8">
          <div className="max-w-5xl mx-auto space-y-8">
            <div className="glass-panel rounded-2xl p-8 flex flex-col items-center justify-center min-h-[400px] border border-border">
              <PieChart className="w-12 h-12 text-muted mb-4" />
              <h2 className="text-xl font-medium text-fg mb-2">Portfolio Overview</h2>
              <p className="text-muted text-sm text-center max-w-md">
                Monitor your investment growth. The behavioral collector dynamically adjusts its scoring thresholds based on the context badge above.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
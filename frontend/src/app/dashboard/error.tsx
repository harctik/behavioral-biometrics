"use client";

import { ShieldAlert, RotateCcw, Home } from "lucide-react";
import Link from "next/link";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
      <div className="max-w-md space-y-6">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center">
          <ShieldAlert className="w-8 h-8 text-red-400" />
        </div>

        <div>
          <h2 className="text-xl font-semibold text-fg mb-2">Something went wrong</h2>
          <p className="text-sm text-muted leading-relaxed">
            A component in the dashboard encountered an error. Your session and data are safe.
          </p>
        </div>

        {error.message && (
          <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-4 text-left">
            <div className="text-[10px] uppercase tracking-wider text-red-400 font-bold mb-1">Error Details</div>
            <p className="text-xs text-muted font-mono break-all">{error.message}</p>
            {error.digest && (
              <p className="text-[9px] text-muted font-mono mt-1">Digest: {error.digest}</p>
            )}
          </div>
        )}

        <div className="flex items-center gap-3 justify-center">
          <button
            onClick={reset}
            className="flex items-center gap-2 px-5 py-2.5 bg-accent-primary text-white text-sm font-medium rounded-xl hover:bg-blue-600 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Try Again
          </button>
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-5 py-2.5 bg-surface-2 border border-border text-fg text-sm font-medium rounded-xl hover:bg-surface-elevated transition-colors"
          >
            <Home className="w-4 h-4" />
            Overview
          </Link>
        </div>

        <p className="text-[9px] text-muted font-mono">
          If this persists, try clearing your browser cache or contact support.
        </p>
      </div>
    </div>
  );
}

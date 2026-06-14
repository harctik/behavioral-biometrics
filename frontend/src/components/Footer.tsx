import Link from "next/link";
import { Shield } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface/80 backdrop-blur-sm py-8 mt-auto z-10 w-full shrink-0">
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-accent-primary/20 flex items-center justify-center border border-accent-primary/30">
              <Shield className="w-4 h-4 text-accent-primary" />
            </div>
            <span className="font-semibold text-fg tracking-wide">AetherAuth</span>
          </div>
          
          <div className="flex items-center gap-6 text-sm text-muted">
            <Link href="/privacy" className="hover:text-fg transition-colors">Privacy Policy</Link>
            <Link href="/compliance" className="hover:text-fg transition-colors">Compliance</Link>
            <Link href="/architecture" className="hover:text-fg transition-colors">Architecture</Link>
            <Link href="/explainability" className="hover:text-fg transition-colors">Explainability</Link>
          </div>
        </div>
        <div className="mt-8 text-center text-xs text-muted/60">
          &copy; {new Date().getFullYear()} AetherAuth Banking Systems. All rights reserved. Not a real bank.
        </div>
      </div>
    </footer>
  );
}

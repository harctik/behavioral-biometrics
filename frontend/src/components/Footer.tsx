import Link from "next/link";
import { Wordmark } from "@/components/Mark";

export function Footer() {
  return (
    <footer className="border-t border-border bg-bg mt-auto w-full shrink-0">
      <div className="max-w-6xl mx-auto px-5 sm:px-8 py-10">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <Wordmark />
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
            <Link href="/privacy" className="hover:text-fg transition-colors">Privacy</Link>
            <Link href="/compliance" className="hover:text-fg transition-colors">Compliance</Link>
            <Link href="/architecture" className="hover:text-fg transition-colors">Architecture</Link>
            <Link href="/explainability" className="hover:text-fg transition-colors">Explainability</Link>
          </nav>
        </div>
        <p className="mt-8 text-xs text-slate-500">
          &copy; {new Date().getFullYear()} AetherAuth. A demonstration project, not a real bank.
        </p>
      </div>
    </footer>
  );
}

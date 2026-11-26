"use client";

import { useEffect } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { getCollector } from "@/lib/behavioral-collector";
import { Footer } from "@/components/Footer";
import { Mark, Wordmark } from "@/components/Mark";
import { RhythmDemo } from "@/components/RhythmDemo";

const signals = [
  {
    name: "Typing rhythm",
    detail: "How long each key is held and the gap before the next one, tracked per pair of keys.",
  },
  {
    name: "Pointer movement",
    detail: "Speed, direction changes and click behaviour as you move around the page.",
  },
  {
    name: "Corrections and pauses",
    detail: "Backspaces, hesitations and pasted text, which look different when someone else is typing.",
  },
];

const steps = [
  { title: "Enrol", detail: "You type a few short phrases. They become the baseline for your profile." },
  { title: "Compare", detail: "While you use the account, new activity is scored against that baseline." },
  { title: "Step up", detail: "If the risk score rises, the app asks for a one-time code or a typing challenge." },
];

export default function LandingPage() {
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("LANDING");
    collector.start();
    return () => collector.stop();
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-bg text-fg">
      <header className="border-b border-border">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 h-16 flex items-center justify-between">
          <Link href="/" aria-label="AetherAuth home">
            <Wordmark />
          </Link>
          <nav aria-label="Main" className="flex items-center gap-5">
            <Link href="/login" className="text-sm text-slate-300 hover:text-fg transition-colors">
              Sign in
            </Link>
            <Link href="/signup" className="text-sm font-semibold bg-fg text-black hover:bg-white px-4 py-2 rounded-md transition-colors">
              Create account
            </Link>
          </nav>
        </div>
      </header>

      <section className="border-b border-border">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-16 lg:py-24 grid lg:grid-cols-[1.05fr_1fr] gap-12 lg:gap-16 items-center">
          <div>
            <h1 className="text-[40px] sm:text-[56px] lg:text-[64px] leading-[1.02] font-semibold tracking-[-0.03em]">
              A password can be stolen. A typing rhythm is harder to copy.
            </h1>
            <p className="mt-6 text-lg leading-relaxed text-muted max-w-xl">
              AetherAuth is a banking demo that keeps checking who is at the keyboard after sign-in,
              using typing and pointer behaviour.
            </p>
            <div className="mt-9 flex flex-col sm:flex-row gap-3">
              <Link href="/signup" className="inline-flex items-center justify-center gap-2 bg-fg text-black hover:bg-white font-semibold px-6 h-12 rounded-md transition-colors">
                Create account
                <ArrowRight className="w-4 h-4" />
              </Link>
              <Link href="/demo" className="inline-flex items-center justify-center border border-slate-700 hover:border-slate-500 font-semibold px-6 h-12 rounded-md transition-colors">
                Sign in to the demo
              </Link>
            </div>
          </div>

          <RhythmDemo />
        </div>
      </section>

      <section className="border-b border-border">
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-16 lg:py-20">
          <h2 className="text-3xl font-semibold tracking-tight">What it looks at</h2>
          <dl className="mt-10 border-t border-border">
            {signals.map((signal) => (
              <div key={signal.name} className="grid md:grid-cols-[1fr_2fr] gap-2 md:gap-8 py-6 border-b border-border">
                <dt className="text-lg font-semibold">{signal.name}</dt>
                <dd className="text-muted leading-relaxed max-w-2xl">{signal.detail}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <section>
        <div className="max-w-6xl mx-auto px-5 sm:px-8 py-16 lg:py-20 grid lg:grid-cols-[1fr_2fr] gap-10">
          <div>
            <Mark className="h-14 w-auto text-fg" />
            <h2 className="mt-6 text-3xl font-semibold tracking-tight">How a session is checked</h2>
          </div>
          <ol className="space-y-px bg-border border-y border-border">
            {steps.map((step, i) => (
              <li key={step.title} className="bg-bg py-6 flex gap-6">
                <span className="font-mono text-sm text-slate-500 pt-1">{i + 1}</span>
                <div>
                  <h3 className="text-lg font-semibold">{step.title}</h3>
                  <p className="mt-1 text-muted leading-relaxed">{step.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <Footer />
    </div>
  );
}

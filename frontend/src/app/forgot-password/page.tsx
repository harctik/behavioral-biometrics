"use client";

import { FormEvent, useState, useEffect } from "react";
import { toast } from "sonner";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { getCollector } from "@/lib/behavioral-collector";
import { AuthShell } from "@/components/auth/AuthShell";
import { AuthButton, AuthInlineMessage, AuthInput } from "@/components/auth/AuthPrimitives";
import { Mail, ArrowLeft } from "lucide-react";

export default function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("FORGOT_PASSWORD");
    collector.reset();
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsLoading(true);

    if (identifier.length < 3) {
      toast.error("Please enter a valid username or email.");
      setIsLoading(false);
      return;
    }

    const isEmail = identifier.includes("@");
    if (isEmail && !identifier.includes(".")) {
      toast.error("Please enter a valid email address.");
      setIsLoading(false);
      return;
    }

    // Gap 6: Flush behavioral data on forgot-password submit
    const collector = getCollector();
    const behavioralData = await collector.flush("forgot_password");

    const payload = isEmail
      ? { email: identifier, behavioral_data: behavioralData }
      : { username: identifier, behavioral_data: behavioralData };

    try {
      const result = await apiClient<{ message?: string; error?: string }>("/v1/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setMessage(
        result.message ??
          "If this account exists, password reset instructions have been sent."
      );
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Unable to process request";
      if (errMsg.toLowerCase().includes("too many") || errMsg.toLowerCase().includes("rate limit") || errMsg.includes("429")) {
        toast.error("Too many attempts. Please wait a moment before trying again.");
      } else if (errMsg.toLowerCase().includes("fetch") || errMsg.toLowerCase().includes("timeout")) {
        toast.error("Network error: Please check your connection.");
      } else {
        toast.error(errMsg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (message) {
    return (
      <AuthShell title="Check your inbox" subtitle="If the account exists, we've sent reset instructions.">
        <div className="text-center space-y-6 mt-4">
          <AuthInlineMessage tone="success">{message}</AuthInlineMessage>
          <Link href="/login" className="block w-full">
            <AuthButton className="w-full">Return to login</AuthButton>
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Forgot password" subtitle="We'll send reset instructions (if the account exists).">
      <div className="mb-6">
        <Link href="/login" className="inline-flex items-center gap-1.5 text-xs text-muted hover:text-white transition-colors group">
          <ArrowLeft className="w-3.5 h-3.5 group-hover:-translate-x-1 transition-transform" />
          Back to login
        </Link>
      </div>
      <form
        onSubmit={handleSubmit}
        className="space-y-4"
      >
        
        

        <div className="relative">
          <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
          <AuthInput
            type="text"
            name="identifier"
            autoComplete="username"
            placeholder="Username or email"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            required
            className="pl-10"
          />
        </div>

        <AuthButton type="submit" disabled={isLoading} className="mt-4 w-full">
          {isLoading ? "Sending..." : "Send reset link"}
        </AuthButton>

        {/* ── Behavioral Profiling Status Bar ── */}
        <div className="mt-6 flex items-center justify-center gap-2.5 text-[10px] text-muted font-mono bg-black/20 border border-border/50 rounded-lg p-3">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_rgba(52,211,153,0.6)]"></span>
          <span>Minimal capture — helps detect bots</span>
        </div>
      </form>
    </AuthShell>
  );
}

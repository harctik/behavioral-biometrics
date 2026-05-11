"use client";

import { FormEvent, useState, useEffect } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { getCollector } from "@/lib/behavioral-collector";
import { AuthShell } from "@/components/auth/AuthShell";
import { AuthButton, AuthInlineMessage, AuthInput } from "@/components/auth/AuthPrimitives";
import { Mail } from "lucide-react";

export default function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // Gap 6: Start behavioral collection on forgot-password page
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("FORGOT_PASSWORD");
    collector.reset();
    collector.start();
    return () => collector.stop();
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setMessage("");
    setIsLoading(true);

    // Gap 6: Flush behavioral data on forgot-password submit
    const collector = getCollector();
    const behavioralData = collector.flush("forgot_password");

    // Backend accepts both username and email - detect which one the user typed
    const isEmail = identifier.includes("@");
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
      setError(err instanceof Error ? err.message : "Unable to process request");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell title="Forgot password" subtitle="We'll send reset instructions (if the account exists).">
      <form
        onSubmit={handleSubmit}
        className="space-y-4"
      >
        {error ? <AuthInlineMessage tone="error">{error}</AuthInlineMessage> : null}
        {message ? <AuthInlineMessage tone="success">{message}</AuthInlineMessage> : null}

        <div className="relative">
          <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
          <AuthInput
            type="text"
            name="identifier"
            autoComplete="username email"
            placeholder="Username or email"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            required
            className="pl-10"
          />
        </div>

        <AuthButton type="submit" disabled={isLoading}>
          {isLoading ? "Sending..." : "Send reset link"}
        </AuthButton>

        <p className="text-center text-xs text-white/60">
          Back to{" "}
          <Link href="/login" className="text-white hover:text-white/70 transition-colors">
            Sign in
          </Link>
        </p>
      </form>
    </AuthShell>
  );
}

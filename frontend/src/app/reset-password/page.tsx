"use client";

import { FormEvent, useMemo, useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";
import { getCollector } from "@/lib/behavioral-collector";
import { AuthShell } from "@/components/auth/AuthShell";
import { AuthButton, AuthInlineMessage, AuthInput } from "@/components/auth/AuthPrimitives";

function ResetPasswordForm() {
  const params = useSearchParams();
  const token = useMemo(() => params.get("token") || "", [params]);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const collector = getCollector();
    collector.setContext("RESET_PASSWORD");
    collector.start();
    return () => collector.stop();
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (newPassword.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    // Client-side complexity hint (backend enforces via Pydantic validator)
    const hasUpper = /[A-Z]/.test(newPassword);
    const hasLower = /[a-z]/.test(newPassword);
    const hasDigit = /\d/.test(newPassword);
    const hasSpecial = /[@$!%*?&]/.test(newPassword);
    if (!hasUpper || !hasLower || !hasDigit || !hasSpecial) {
      setError("Password must contain uppercase, lowercase, digit, and special character (@$!%*?&).");
      return;
    }

    setIsLoading(true);
    try {
      await apiClient<{ success: boolean }>("/v1/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      setMessage("Password updated. You can sign in now.");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setIsLoading(false);
    }
  };

  const passwordsMatch = confirmPassword.length === 0 || newPassword === confirmPassword;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error ? <AuthInlineMessage tone="error">{error}</AuthInlineMessage> : null}
      {message ? <AuthInlineMessage tone="success">{message}</AuthInlineMessage> : null}
      <div>
        <AuthInput
          type="password"
          name="new_password"
          autoComplete="new-password"
          placeholder="New password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
        />
        <p className="text-[10px] text-white/40 mt-1.5 px-1">
          Min 8 chars · uppercase · lowercase · digit · special (@$!%*?&amp;)
        </p>
      </div>
      <div>
        <AuthInput
          type="password"
          name="confirm_password"
          autoComplete="new-password"
          placeholder="Confirm new password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
        />
        {!passwordsMatch && (
          <p className="text-[10px] text-red-400 mt-1 px-1">Passwords do not match</p>
        )}
      </div>
      <AuthButton type="submit" disabled={isLoading || !token || !passwordsMatch}>
        {isLoading ? "Updating..." : "Update password"}
      </AuthButton>
      <p className="text-center text-xs text-white/60">
        Back to{" "}
        <Link href="/login" className="text-white hover:text-white/70 transition-colors">
          Sign in
        </Link>
      </p>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <AuthShell title="Reset password" subtitle="Set a new password for your account.">
      <Suspense fallback={<div className="text-white/60 text-xs text-center py-4">Loading...</div>}>
        <ResetPasswordForm />
      </Suspense>
    </AuthShell>
  );
}

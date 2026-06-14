"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { apiClient } from "@/lib/api-client";
import { AuthShell } from "@/components/auth/AuthShell";
import { AuthButton } from "@/components/auth/AuthPrimitives";
import Link from "next/link";
import { CheckCircle2, Loader2, ShieldAlert } from "lucide-react";

import { Suspense } from "react";

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [isVerifying, setIsVerifying] = useState(true);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [mfaSecret, setMfaSecret] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setIsVerifying(false);
      setError("No verification token found.");
      return;
    }

    let isMounted = true;

    async function verify() {
      try {
        const result = await apiClient<{
          data?: { mfa_secret?: string };
          success: boolean;
          error?: string;
        }>("/v1/auth/verify-email", {
          method: "POST",
          body: JSON.stringify({ token }),
        });

        if (isMounted) {
          setIsVerifying(false);
          if (result.success) {
            setSuccess(true);
            if (result.data?.mfa_secret) {
              setMfaSecret(result.data.mfa_secret);
            }
          } else {
            setError(result.error || "Verification failed.");
          }
        }
      } catch (err: unknown) {
        if (isMounted) {
          setIsVerifying(false);
          const raw = err instanceof Error ? err.message : "Verification failed";
          setError(raw);
        }
      }
    }

    verify();

    return () => {
      isMounted = false;
    };
  }, [token]);

  if (isVerifying) {
    return (
      <AuthShell title="Verifying Email..." subtitle="Please wait while we verify your email address.">
        <div className="flex flex-col items-center justify-center p-8 space-y-4 text-muted">
          <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
          <p>Verifying your email...</p>
        </div>
      </AuthShell>
    );
  }

  if (error) {
    return (
      <AuthShell title="Verification Failed" subtitle="We couldn't verify your email address.">
        <div className="space-y-6 text-center">
          <div className="mx-auto w-16 h-16 bg-red-500/10 flex items-center justify-center rounded-full border border-red-500/20">
            <ShieldAlert className="w-8 h-8 text-red-500" />
          </div>
          <div className="text-sm text-red-400 bg-red-500/10 p-4 rounded-xl border border-red-500/20">
            {error}
          </div>
          <Link href="/login" className="block w-full mt-4">
            <AuthButton className="w-full">Return to Login</AuthButton>
          </Link>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Email Verified" subtitle="Your email address has been successfully verified.">
      <div className="space-y-6 text-center">
        <div className="mx-auto w-16 h-16 bg-emerald-500/10 flex items-center justify-center rounded-full border border-emerald-500/20">
          <CheckCircle2 className="w-8 h-8 text-emerald-400" />
        </div>
        
        {mfaSecret && (
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-4 text-left">
            <h4 className="text-xs font-semibold text-amber-400 uppercase tracking-wider mb-2">Save MFA Secret</h4>
            <div className="flex items-center gap-2">
              <p className="flex-1 text-xs text-amber-400/80 font-mono bg-black/40 p-2 rounded">{mfaSecret}</p>
              <button 
                onClick={() => navigator.clipboard.writeText(mfaSecret)} 
                className="bg-black/40 hover:bg-black/60 text-amber-400/80 p-2 rounded transition-colors text-xs font-medium"
              >
                Copy
              </button>
            </div>
          </div>
        )}
        
        <Link href="/login" className="block w-full">
          <AuthButton className="w-full">Continue to Login</AuthButton>
        </Link>
      </div>
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<AuthShell title="Loading..." subtitle=""><div /></AuthShell>}>
      <VerifyEmailContent />
    </Suspense>
  );
}

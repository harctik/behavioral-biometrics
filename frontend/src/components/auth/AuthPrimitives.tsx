"use client";

import React from "react";
import { cn } from "@/lib/utils";

export function AuthInput(props: React.ComponentProps<"input">) {
  const { className, ...rest } = props;
  return (
    <input
      className={cn(
        "w-full h-11 rounded-lg border border-slate-700/50 bg-slate-900/50 px-4 text-sm text-slate-100 placeholder:text-slate-500",
        "focus:outline-none focus:border-blue-500/50 focus:bg-slate-900/80 focus:ring-4 focus:ring-blue-500/10 transition-all shadow-inner",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        className
      )}
      {...rest}
    />
  );
}

export function AuthButton(props: React.ComponentProps<"button">) {
  const { className, ...rest } = props;
  return (
    <button
      className={cn(
        "w-full relative overflow-hidden bg-blue-600 hover:bg-blue-500 text-white font-medium h-11 rounded-lg shadow-[0_0_15px_rgba(37,99,235,0.2)] hover:shadow-[0_0_25px_rgba(37,99,235,0.4)]",
        "transition-all duration-300 flex items-center justify-center border border-blue-400/20",
        "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-blue-600 disabled:hover:shadow-none",
        className
      )}
      {...rest}
    />
  );
}

export function AuthInlineMessage({
  tone,
  children,
}: {
  tone: "error" | "success" | "info";
  children: React.ReactNode;
}) {
  const toneClasses =
    tone === "error"
      ? "text-red-400 bg-red-950/30 border-red-900/50"
      : tone === "success"
        ? "text-emerald-400 bg-emerald-950/30 border-emerald-900/50"
        : "text-blue-400 bg-blue-950/30 border-blue-900/50";

  return (
    <div className={cn("text-sm text-center border rounded-lg py-3 px-4 shadow-sm", toneClasses)}>
      {children}
    </div>
  );
}

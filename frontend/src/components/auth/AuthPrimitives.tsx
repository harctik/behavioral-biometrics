"use client";

import React from "react";
import { cn } from "@/lib/utils";

export function AuthInput(props: React.ComponentProps<"input">) {
  const { className, ...rest } = props;
  return (
    <input
      className={cn(
        "w-full h-11 rounded-md border border-slate-700 px-3.5 text-sm text-fg placeholder:text-slate-600",
        "focus:border-fg transition-colors",
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
        "w-full bg-fg hover:bg-white text-black font-semibold h-11 rounded-md",
        "transition-colors flex items-center justify-center gap-2",
        "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-fg",
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

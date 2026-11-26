"use client";

import React from "react";
import Link from "next/link";
import { Mark } from "@/components/Mark";

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center px-4 py-10 bg-bg">
      <div className="w-full max-w-[420px]">
        <Link href="/" aria-label="AetherAuth home" className="inline-block text-fg mb-10">
          <Mark className="h-10 w-auto" />
        </Link>

        <h1 className="text-[28px] leading-tight font-semibold tracking-tight text-fg">{title}</h1>
        {subtitle && <p className="mt-2 text-sm leading-relaxed text-muted">{subtitle}</p>}

        <div className="mt-8">{children}</div>
      </div>
    </div>
  );
}

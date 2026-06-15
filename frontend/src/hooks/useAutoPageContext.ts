"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { getCollector, type PageContext } from "@/lib/behavioral-collector";

/**
 * Automatically sets the BehavioralCollector's page context
 * based on the current URL. This ensures all behavioral events
 * are tagged with the correct page context for downstream
 * analysis by the ML ensemble.
 */
export function useAutoPageContext() {
  const pathname = usePathname();

  useEffect(() => {
    const map: Record<string, PageContext> = {
      "/login": "LOGIN",
      "/signup": "SIGNUP",
      "/otp": "OTP_VERIFY",
      "/dashboard/transfers": "TRANSFERS_PAGE",
      "/dashboard/settings": "SETTINGS_PAGE",
      "/dashboard/investments": "INVESTMENTS_PAGE",
      "/dashboard/statements": "STATEMENTS_PAGE",
      "/dashboard/cards": "CARDS_PAGE",
      "/dashboard": "DASHBOARD",
      "/challenge": "CHALLENGE",
      "/calibration": "CALIBRATION",
      "/forgot-password": "FORGOT_PASSWORD",
      "/reset-password": "RESET_PASSWORD",
      "/compliance": "COMPLIANCE",
      "/explainability": "EXPLAINABILITY",
      "/admin": "ADMIN",
      "/privacy": "PRIVACY",
      "/": "LANDING",
    };

    // Match longest prefix first
    let ctx: PageContext = "LANDING";
    const sortedKeys = Object.keys(map).sort((a, b) => b.length - a.length);
    for (const key of sortedKeys) {
      if (pathname === key || (key !== "/" && pathname.startsWith(key + "/"))) {
        ctx = map[key];
        break;
      }
    }

    try {
      const collector = getCollector();
      collector.setContext(ctx);
    } catch {}
  }, [pathname]);
}

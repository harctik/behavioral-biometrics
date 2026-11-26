import type { Metadata } from "next";
import { Schibsted_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ServiceWorkerRegistration } from "@/components/ServiceWorkerRegistration";
import { NavBar } from "@/components/NavBar";
import { BehavioralProvider } from "@/components/BehavioralProvider";
import { SessionTimeoutWarning } from "@/components/SessionTimeoutWarning";
import { BehavioralIntelligenceOverlay } from "@/components/behavioral/BehavioralIntelligenceOverlay";
import { GlobalPasteWarning } from "@/components/behavioral/GlobalPasteWarning";
import { SpeedInsights } from "@vercel/speed-insights/next";

import { Footer } from "@/components/Footer";
import { Toaster } from "sonner";

const schibsted = Schibsted_Grotesk({
  variable: "--font-schibsted",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AetherAuth · Behavioral authentication",
  description:
    "A banking demo that keeps checking who is at the keyboard, using typing and pointer behaviour.",
  other: {
    "theme-color": "#000000",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${schibsted.variable} ${jetbrainsMono.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex flex-col relative">
        <a href="#main-content" className="skip-to-content">Skip to main content</a>
        <ServiceWorkerRegistration />
        <BehavioralProvider />
        <SessionTimeoutWarning />
        <main id="main-content" className="flex-1 relative z-10" role="main">
          {children}
        </main>
        <BehavioralIntelligenceOverlay />
        <GlobalPasteWarning />
        <Toaster theme="dark" position="bottom-right" />
        <div aria-live="polite" aria-atomic="true" className="sr-only" id="a11y-announcer" />
        <SpeedInsights />
      </body>
    </html>
  );
}


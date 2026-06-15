import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
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

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "BCA - Behavioral Biometrics Authentication",
  description:
    "Banking-grade continuous authentication using keystroke dynamics, mouse behavior, and ensemble ML models.",
  other: {
    "theme-color": "#030712",
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
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased dark`}
    >
      <body className="min-h-full flex flex-col relative bg-grid-pattern">
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


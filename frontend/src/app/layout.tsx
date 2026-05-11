import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ServiceWorkerRegistration } from "@/components/ServiceWorkerRegistration";
import { NavBar } from "@/components/NavBar";
import { BehavioralProvider } from "@/components/BehavioralProvider";
import { SessionTimeoutWarning } from "@/components/SessionTimeoutWarning";
import { SpeedInsights } from "@vercel/speed-insights/next";

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
        <ServiceWorkerRegistration />
        <BehavioralProvider />
        <SessionTimeoutWarning />
        <NavBar />
        <main className="flex-1 relative z-10">
          {children}
        </main>
        <SpeedInsights />
      </body>
    </html>
  );
}


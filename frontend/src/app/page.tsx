"use client";

import { useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Shield, Keyboard, MousePointer2, Brain, ChevronRight, Activity, Fingerprint } from "lucide-react";
import { getCollector } from "@/lib/behavioral-collector";

export default function LandingPage() {
  useEffect(() => {
    const collector = getCollector();
    collector.setContext("LANDING");
    collector.start();
    return () => collector.stop();
  }, []);

  const containerVariants: any = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const itemVariants: any = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } }
  };

  return (
    <div className="min-h-screen text-slate-200 overflow-hidden relative">
      {/* Background Effects */}
      <div className="absolute top-0 inset-x-0 h-[500px] bg-gradient-to-b from-blue-900/20 to-transparent pointer-events-none" />
      <div className="absolute top-1/4 -left-64 w-[600px] h-[600px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 -right-64 w-[600px] h-[600px] bg-emerald-600/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Navbar */}
      <nav className="relative z-10 flex items-center justify-between px-6 py-4 max-w-7xl mx-auto">
        <div className="flex items-center gap-2">
          <Shield className="w-8 h-8 text-blue-500" />
          <span className="font-bold text-xl tracking-tight text-white">AetherAuth<span className="text-blue-500">Secure</span></span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/login" className="text-sm font-semibold text-slate-300 hover:text-white transition-colors">
            Sign In
          </Link>
          <Link href="/signup" className="text-sm font-bold bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-xl transition-all shadow-[0_0_15px_rgba(37,99,235,0.3)]">
            Get Started
          </Link>
        </div>
      </nav>

      <main className="relative z-10 max-w-7xl mx-auto px-6 pt-20 pb-32">
        {/* Hero Section */}
        <div className="flex flex-col lg:flex-row items-center gap-16">
          <motion.div 
            className="flex-1 space-y-8"
            variants={containerVariants}
            initial="hidden"
            animate="show"
          >
            <motion.div variants={itemVariants} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-sm font-medium">
              <Activity className="w-4 h-4" />
              <span>Next-Gen RBI Compliant Security</span>
            </motion.div>

            <motion.h1 variants={itemVariants} className="text-5xl lg:text-7xl font-bold tracking-tight text-white leading-tight">
              Authentication That <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">Understands You.</span>
            </motion.h1>

            <motion.p variants={itemVariants} className="text-lg text-slate-400 leading-relaxed max-w-xl">
              AetherAuth leverages continuous behavioral biometrics. We analyze your keystroke dynamics, mouse movements, and cognitive patterns to protect your account without friction.
            </motion.p>

            <motion.div variants={itemVariants} className="flex flex-col sm:flex-row gap-4 pt-4">
              <Link href="/signup" className="flex items-center justify-center gap-2 bg-white hover:bg-slate-100 text-slate-900 font-bold px-8 py-4 rounded-xl transition-all shadow-[0_0_20px_rgba(255,255,255,0.1)] text-lg">
                Create Secure Account
                <ChevronRight className="w-5 h-5" />
              </Link>
              <Link href="/login" className="flex items-center justify-center gap-2 bg-slate-900/50 hover:bg-slate-800 text-white border border-slate-700 font-bold px-8 py-4 rounded-xl transition-all text-lg backdrop-blur-md">
                View Live Demo
              </Link>
            </motion.div>
          </motion.div>

          {/* Hero Visual */}
          <motion.div 
            className="flex-1 w-full max-w-lg lg:max-w-none relative"
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, delay: 0.2 }}
          >
            <div className="relative rounded-3xl border border-slate-800 bg-slate-900/50 backdrop-blur-xl p-8 overflow-hidden shadow-2xl">
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-emerald-500/5" />
              
              <div className="relative space-y-6">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div className="flex items-center gap-3">
                    <Fingerprint className="w-6 h-6 text-emerald-400" />
                    <span className="font-mono text-sm text-slate-300">Live Behavioral Analysis</span>
                  </div>
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-slate-700" />
                    <div className="w-3 h-3 rounded-full bg-slate-700" />
                    <div className="w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]" />
                  </div>
                </div>

                <div className="space-y-4">
                  {[
                    { icon: <Keyboard className="w-5 h-5"/>, label: "Keystroke Dynamics", val: "99.2%", color: "text-blue-400", bar: "bg-blue-500" },
                    { icon: <MousePointer2 className="w-5 h-5"/>, label: "Pointer Biometrics", val: "98.5%", color: "text-emerald-400", bar: "bg-emerald-500" },
                    { icon: <Brain className="w-5 h-5"/>, label: "Cognitive Patterns", val: "97.8%", color: "text-amber-400", bar: "bg-amber-500" },
                  ].map((stat, i) => (
                    <div key={i} className="bg-slate-950/50 rounded-xl p-4 border border-slate-800">
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3 text-slate-300">
                          <div className={`p-2 rounded-lg bg-slate-900 ${stat.color}`}>
                            {stat.icon}
                          </div>
                          <span className="font-medium text-sm">{stat.label}</span>
                        </div>
                        <span className="font-mono text-sm text-slate-400">{stat.val} Confidence</span>
                      </div>
                      <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                        <motion.div 
                          className={`h-full ${stat.bar}`}
                          initial={{ width: 0 }}
                          animate={{ width: stat.val }}
                          transition={{ duration: 1.5, delay: 0.5 + (i * 0.2), ease: "easeOut" }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            
            {/* Floating badge */}
            <motion.div 
              className="absolute -bottom-6 -left-6 bg-slate-900 border border-slate-700 p-4 rounded-2xl shadow-xl flex items-center gap-4"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.2 }}
            >
              <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center border border-emerald-500/30">
                <Shield className="w-6 h-6 text-emerald-400" />
              </div>
              <div>
                <div className="text-sm font-bold text-white">Identity Verified</div>
                <div className="text-xs text-slate-400">Zero-friction security</div>
              </div>
            </motion.div>
          </motion.div>
        </div>

        {/* Features Section */}
        <div className="mt-32 grid grid-cols-1 md:grid-cols-3 gap-8">
          {[
            {
              title: "Continuous Authentication",
              desc: "Security doesn't stop at login. We continuously verify your identity in the background using behavioral ML models.",
              icon: <Activity className="w-6 h-6" />
            },
            {
              title: "Zero-Friction Experience",
              desc: "No more annoying captchas or frequent OTPs. Step-up authentication is only triggered when behavioral anomalies are detected.",
              icon: <Brain className="w-6 h-6" />
            },
            {
              title: "Regulatory Compliant",
              desc: "Built to exceed RBI Master Directions 2021, PCI DSS 4.0, and DPDP Act 2023 requirements with full explainability.",
              icon: <Shield className="w-6 h-6" />
            }
          ].map((feature, i) => (
            <motion.div 
              key={i}
              className="bg-slate-900/50 border border-slate-800 rounded-2xl p-8 hover:bg-slate-800/50 transition-colors"
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
            >
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center mb-6">
                {feature.icon}
              </div>
              <h3 className="text-xl font-bold text-white mb-3">{feature.title}</h3>
              <p className="text-slate-400 leading-relaxed text-sm">
                {feature.desc}
              </p>
            </motion.div>
          ))}
        </div>
      </main>
    </div>
  );
}

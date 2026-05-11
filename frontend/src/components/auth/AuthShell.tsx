"use client";

import React from "react";
import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";

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
    <div className="min-h-screen w-full relative overflow-hidden flex items-center justify-center p-6 bg-bg bg-grid-pattern">
      {/* Background Orbs */}
      <div className="absolute top-1/4 -left-64 w-[500px] h-[500px] bg-accent-primary/10 rounded-full blur-[120px] pointer-events-none" />
      <div className="absolute bottom-1/4 -right-64 w-[500px] h-[500px] bg-accent-success/10 rounded-full blur-[120px] pointer-events-none" />

      {/* Cyber-ring Scanner Animation */}
      <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] pointer-events-none opacity-20">
        <motion.div
          className="absolute inset-0 rounded-full border-[1px] border-accent-primary/20"
          animate={{ rotate: 360, scale: [1, 1.05, 1] }}
          transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
        />
        <motion.div
          className="absolute inset-8 rounded-full border-[1px] border-accent-success/20 border-dashed"
          animate={{ rotate: -360, scale: [1, 0.95, 1] }}
          transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-md relative z-10"
      >
        <div className="glass-panel-glow rounded-3xl p-8 relative overflow-hidden">
          {/* Top Edge Glow line */}
          <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-accent-primary to-transparent opacity-50" />
          
          <div className="flex flex-col items-center text-center space-y-3 mb-8 relative">
            <motion.div 
              className="w-14 h-14 rounded-2xl bg-black/40 border border-border flex items-center justify-center text-accent-primary mb-2 relative overflow-hidden"
              whileHover={{ scale: 1.05 }}
              transition={{ type: "spring", stiffness: 400, damping: 10 }}
            >
              <div className="absolute inset-0 bg-accent-primary/10" />
              <ShieldCheck size={28} className="relative z-10" />
            </motion.div>
            
            <h1 className="text-2xl font-bold tracking-tight text-fg">
              {title}
            </h1>
            {subtitle && (
              <p className="text-muted text-sm leading-relaxed max-w-[280px]">
                {subtitle}
              </p>
            )}
          </div>

          <div className="relative">
            {children}
          </div>
        </div>
      </motion.div>
    </div>
  );
}

"use client";

import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Fingerprint, Lock, Activity } from "lucide-react";

interface BiometricScannerProps {
  /** Whether the scanner overlay is visible */
  isVisible: boolean;
  /** Status text shown during scanning */
  status?: string;
  /** Current progress 0-100 (optional, for determinate mode) */
  progress?: number;
}

/**
 * Full-screen cinematic "Biometric Scanning" overlay.
 * Replaces a standard spinner when the user submits login/signup.
 */
export function BiometricScanner({
  isVisible,
  status = "Analyzing behavioral session...",
  progress,
}: BiometricScannerProps) {
  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-0 z-[200] flex items-center justify-center"
          style={{ background: "rgba(3, 7, 18, 0.85)", backdropFilter: "blur(12px)" }}
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="flex flex-col items-center text-center max-w-xs"
          >
            {/* Scanner visual */}
            <div className="relative w-32 h-32 mb-8">
              {/* Outer ring pulse */}
              <motion.div
                className="absolute inset-0 rounded-full border border-blue-500/30"
                animate={{ scale: [1, 1.25], opacity: [0.6, 0] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
              />
              {/* Middle ring pulse (delayed) */}
              <motion.div
                className="absolute inset-2 rounded-full border border-purple-500/20"
                animate={{ scale: [1, 1.15], opacity: [0.4, 0] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut", delay: 0.4 }}
              />
              {/* Rotating arc */}
              <motion.div
                className="absolute inset-0 rounded-full"
                style={{
                  border: "2px solid transparent",
                  borderTopColor: "rgba(59, 130, 246, 0.7)",
                  borderRightColor: "rgba(139, 92, 246, 0.4)",
                }}
                animate={{ rotate: 360 }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
              />
              {/* Central icon */}
              <div className="absolute inset-0 flex items-center justify-center">
                <motion.div
                  animate={{ scale: [1, 1.08, 1], opacity: [0.8, 1, 0.8] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <Fingerprint className="w-12 h-12 text-blue-400" strokeWidth={1.5} />
                </motion.div>
              </div>
              {/* Horizontal scan line */}
              <motion.div
                className="absolute left-2 right-2 h-[1px] bg-gradient-to-r from-transparent via-blue-400 to-transparent"
                style={{ boxShadow: "0 0 8px rgba(59, 130, 246, 0.6)" }}
                animate={{ top: ["10%", "90%", "10%"] }}
                transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
              />
            </div>

            {/* Status text */}
            <div className="flex items-center gap-2 mb-4">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-blue-400"
                  animate={{ opacity: [0.2, 1, 0.2] }}
                  transition={{ duration: 1, repeat: Infinity, delay: i * 0.25 }}
                />
              ))}
              <span className="text-sm text-slate-300 font-medium">{status}</span>
            </div>

            {/* Progress bar (optional) */}
            {progress !== undefined && (
              <div className="w-48 h-1 bg-white/10 rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            )}

            {/* Security badges */}
            <div className="flex items-center gap-4 mt-6 text-[10px] text-slate-500 font-mono">
              <span className="flex items-center gap-1">
                <Lock className="w-3 h-3" /> AES-256
              </span>
              <span className="flex items-center gap-1">
                <Activity className="w-3 h-3" /> Telemetry OK
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

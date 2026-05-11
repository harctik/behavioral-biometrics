'use client';

import Link from 'next/link';
import { ShieldOff, Home, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <motion.div 
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 text-center shadow-2xl"
      >
        <div className="w-16 h-16 bg-amber-500/20 rounded-2xl flex items-center justify-center mx-auto mb-6">
          <ShieldOff className="w-8 h-8 text-amber-500" />
        </div>

        <h2 className="text-6xl font-bold text-white mb-2">404</h2>
        <p className="text-xl font-semibold text-white/80 mb-2">Page Not Found</p>
        <p className="text-slate-400 text-sm mb-8">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
          This request has been logged for security monitoring.
        </p>

        <div className="space-y-3">
          <Link
            href="/dashboard"
            className="w-full bg-white text-slate-900 font-bold py-3.5 rounded-xl hover:bg-slate-100 transition-colors flex items-center justify-center gap-2 no-underline"
          >
            <Home className="w-4 h-4" />
            Go to Dashboard
          </Link>

          <Link
            href="/login"
            className="w-full bg-slate-800 text-white font-bold py-3.5 rounded-xl hover:bg-slate-700 transition-colors flex items-center justify-center gap-2 no-underline"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Login
          </Link>
        </div>
      </motion.div>
    </div>
  );
}

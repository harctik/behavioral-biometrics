'use client';

import { useEffect } from 'react';
import { ShieldAlert, RefreshCcw } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Application Error:', error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <motion.div 
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        className="max-w-md w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 text-center shadow-2xl"
      >
        <div className="w-16 h-16 bg-red-500/20 rounded-2xl flex items-center justify-center mx-auto mb-6">
          <ShieldAlert className="w-8 h-8 text-red-500" />
        </div>
        
        <h2 className="text-2xl font-bold text-white mb-2">Something went wrong</h2>
        <p className="text-slate-400 text-sm mb-8">
          A critical error occurred in the authentication pipeline. This session has been secured and the error has been logged.
        </p>
        
        <div className="space-y-3">
          <button
            onClick={() => reset()}
            className="w-full bg-white text-slate-900 font-bold py-3.5 rounded-xl hover:bg-slate-100 transition-colors flex items-center justify-center gap-2"
          >
            <RefreshCcw className="w-4 h-4" />
            Try again
          </button>
          
          <button
            onClick={() => window.location.href = '/'}
            className="w-full bg-slate-800 text-white font-bold py-3.5 rounded-xl hover:bg-slate-700 transition-colors"
          >
            Return to Dashboard
          </button>
        </div>
        
        {process.env.NODE_ENV === 'development' && (
          <div className="mt-8 pt-6 border-t border-slate-800 text-left">
            <p className="text-[10px] font-mono text-red-400 break-all">
              {error.message}
            </p>
          </div>
        )}
      </motion.div>
    </div>
  );
}

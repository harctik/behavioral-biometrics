"use client";
import { getCsrfToken, getSessionId } from "@/lib/auth-utils";


import React, { createContext, useContext, useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { getCollector } from "@/lib/behavioral-collector";

interface DigraphProfileInfo {
  has_profile: boolean;
  per_key_count: number;
  per_digraph_count: number;
  updates_count: number;
  confidence: number;
  created_at?: string;
  last_updated?: string;
}

interface TelemetryContextValue {
  score: number | null;
  events: { time: string; msg: string }[];
  backendMetrics: any;
  enrollment: { enrolled: boolean; phase: string; completed: number; required: number } | null;
  digraphProfile: DigraphProfileInfo | null;
}

const TelemetryContext = createContext<TelemetryContextValue>({
  score: null,
  events: [],
  backendMetrics: null,
  enrollment: null,
  digraphProfile: null,
});

export function TelemetryProvider({ children }: { children: React.ReactNode }) {
  const [score, setScore] = useState<number | null>(null);
  const [events, setEvents] = useState<{ time: string; msg: string }[]>([]);
  const [backendMetrics, setBackendMetrics] = useState<any>(null);
  const [enrollment, setEnrollment] = useState<{ enrolled: boolean; phase: string; completed: number; required: number } | null>(null);
  const [digraphProfile, setDigraphProfile] = useState<DigraphProfileInfo | null>(null);



  useEffect(() => {
    let isMounted = true;
    const collector = getCollector();
    collector.start();

    let abortController = new AbortController();

    const streamMetrics = async () => {
      if (!isMounted) return;
      try {
        const freshCsrf = getCsrfToken();
        // Skip stream connection when not authenticated
        if (!freshCsrf || !document.cookie.includes("csrf_access_token=")) {
          setTimeout(() => { if (isMounted) streamMetrics(); }, 5000);
          return;
        }

        const res = await fetch("/api/v1/session/metrics/stream", {
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-TOKEN": freshCsrf
          },
          signal: abortController.signal
        });
        
        if (!res.ok) {
          // Silently retry on auth failures (401/403) or server errors
          setTimeout(() => {
            if (isMounted) {
              abortController = new AbortController();
              streamMetrics();
            }
          }, 5000);
          return;
        }
        if (!res.body) return;

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        
        while (isMounted) {
          const { done, value } = await reader.read();
          if (done) break;
          
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const metrics = JSON.parse(line.substring(6));
                const val = metrics.authenticity_score || 0;
                setScore(val <= 1 ? Math.round(val * 100) : Math.round(val));
                setBackendMetrics(metrics);
                
                if (metrics.enrollment && metrics.enrollment.enrollment_phase) {
                  setEnrollment({
                    enrolled: metrics.enrollment.enrolled || false,
                    phase: metrics.enrollment.enrollment_phase,
                    completed: metrics.enrollment.sessions_completed || 0,
                    required: metrics.enrollment.sessions_required || 5
                  });
                }
                if (metrics.digraph_profile) {
                  setDigraphProfile(metrics.digraph_profile);
                }
                
                setEvents(prev => {
                  const newEvent = { 
                    time: new Date().toLocaleTimeString(), 
                    msg: `KS:${metrics.keystroke_count} Ptr:${metrics.mouse_count} Hold:${Math.round(metrics.average_hold_time || 0)}ms Cor:${metrics.corrections_count || 0}`
                  };
                  if (prev.length === 0 || prev[0].msg !== newEvent.msg) {
                    return [newEvent, ...prev].slice(0, 4);
                  }
                  return prev;
                });
              } catch (e) {
                // Ignore parse errors on incomplete chunks
              }
            }
          }
        }
      } catch (err: any) {
        if (isMounted && err.name !== 'AbortError') {
          setTimeout(() => { 
            if (isMounted) {
              abortController = new AbortController();
              streamMetrics(); 
            }
          }, 5000);
        }
      }
    };
    
    streamMetrics();

    const metricsInterval = setInterval(async () => {
      if (!isMounted) return;
      try {
        const csrf = getCsrfToken();
        if (!csrf || !document.cookie.includes("csrf_access_token=")) return;
        const mRes = await fetch("/api/v1/session/metrics", { headers: { "X-CSRF-TOKEN": csrf } });
        if (!mRes.ok) return;
        const mData = await mRes.json();
        setBackendMetrics(mData);
        const val = mData.authenticity_score || 0;
        setScore(val <= 1 ? Math.round(val * 100) : val);
        if (mData.enrollment && mData.enrollment.enrollment_phase) {
          setEnrollment({
            enrolled: mData.enrollment.enrolled || false,
            phase: mData.enrollment.enrollment_phase,
            completed: mData.enrollment.sessions_completed || 0,
            required: mData.enrollment.sessions_required || 5
          });
        }
        if (mData.digraph_profile) {
          setDigraphProfile(mData.digraph_profile);
        }
      } catch {}
    }, 5000);

    return () => {
      isMounted = false;
      collector.stop();
      abortController.abort();
      clearInterval(metricsInterval);
    };
  }, []);

  // Global Risk Escalation Listener
  const lastRiskAlertTime = useRef<number>(0);
  
  useEffect(() => {
    if (backendMetrics && backendMetrics.risk_score !== undefined) {
      const riskScore = backendMetrics.risk_score;
      if (riskScore > 0.75) {
        const now = Date.now();
        // Prevent spamming alerts; only show once every 30 seconds
        if (now - lastRiskAlertTime.current > 30000) {
          toast.error("High Risk Activity Detected", {
            description: "Unusual behavioral patterns have elevated your risk score. Certain operations may require step-up authentication.",
            duration: 5000,
          });
          lastRiskAlertTime.current = now;
        }
      }
    }
  }, [backendMetrics]);

  return (
    <TelemetryContext.Provider value={{ score, events, backendMetrics, enrollment, digraphProfile }}>
      {children}
    </TelemetryContext.Provider>
  );
}

export function useTelemetry() {
  return useContext(TelemetryContext);
}

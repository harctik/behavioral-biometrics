// Shapes of the backend responses the UI reads. Fields are optional where the
// screens already treat them as possibly missing.

export interface DigraphProfileInfo {
  has_profile: boolean;
  per_key_count: number;
  per_digraph_count: number;
  updates_count: number;
  confidence: number;
  created_at?: string;
  last_updated?: string;
}

export interface EnsembleMetrics {
  ensemble_action?: string;
  ensemble_risk?: number;
  ensemble_flags?: string[];
  cognitive_analysis?: { cognitive_risk?: number };
  duress_score?: number;
  liveness_score?: number;
  challenge_risk?: number;
  device_risk?: number;
  replay_risk?: number;
  drift_risk?: number;
  weighted_match_score?: number;
  digraph_match_score?: number;
}

export interface SessionMetrics {
  authenticity_score?: number;
  risk_score?: number;
  keystroke_count?: number;
  mouse_count?: number;
  average_hold_time?: number;
  corrections_count?: number;
  feature_richness?: number;
  category_scores?: Record<string, number>;
  cognitive_anomaly?: boolean;
  context?: string;
  ensemble?: EnsembleMetrics;
  enrollment?: {
    enrolled?: boolean;
    enrollment_phase?: string;
    sessions_completed?: number;
    sessions_required?: number;
  };
  digraph_profile?: DigraphProfileInfo;
}

export interface ApiBeneficiary {
  id: string;
  name: string;
  account: string;
}

export interface ApiTransaction {
  id?: string;
  transaction_id?: string;
  date: string;
  amount: number | string;
  type?: string;
  transaction_type?: string;
  merchant?: string;
  operation?: string;
  description?: string;
  category?: string;
  status?: string;
  decision?: string;
}

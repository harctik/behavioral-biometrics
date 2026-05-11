import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { behavioral_snapshot, confidence_score } = body;
    
    // Mock backend scoring for faculty demo:
    // Simply check if there's enough data and the local confidence is high enough
    const ksCount = behavioral_snapshot?.keystroke_events?.length || 0;
    const msCount = behavioral_snapshot?.mouse_events?.length || 0;
    
    if (confidence_score >= 75 || (ksCount > 15 || msCount > 50)) {
      return NextResponse.json({
        verified: true,
        confidence: (confidence_score / 100) || 0.87,
        method: "behavioral",
        signals_used: ["keystroke_rhythm", "typing_speed", "mouse_dynamics"]
      });
    } else {
      return NextResponse.json({
        verified: false,
        confidence: (confidence_score / 100) || 0.41,
        reason: "keystroke_rhythm_mismatch",
        fallback: "otp"
      });
    }
  } catch (error) {
    return NextResponse.json({ error: "Verification failed" }, { status: 500 });
  }
}

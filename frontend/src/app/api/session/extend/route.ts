import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { behavioral_data } = body;
    
    // Mock backend extending session and checking behavioral data
    const ksCount = behavioral_data?.keystroke_events?.length || 0;
    const msCount = behavioral_data?.mouse_events?.length || 0;
    
    if (ksCount > 5 || msCount > 10) {
      return NextResponse.json({
        extended: true,
        step_up_required: false
      });
    } else {
      // Not enough interaction, trigger step up challenge
      return NextResponse.json({
        extended: true,
        step_up_required: true
      });
    }
  } catch (error) {
    return NextResponse.json({ error: "Extension failed" }, { status: 500 });
  }
}

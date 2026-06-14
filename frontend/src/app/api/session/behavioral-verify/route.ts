import { NextResponse } from "next/server";

export async function POST(req: Request) {
  try {
    const rawBody = await req.text();
    if (rawBody.length > 500 * 1024) { // 500KB limit
      return NextResponse.json({ error: "Payload too large" }, { status: 413 });
    }
    const payload = JSON.parse(rawBody);

    // Fix: correct cookie name is "access_token_cookie", not "access_token"
    const tokenCookie = req.headers.get("cookie")?.split(";")
      .find(c => c.trim().startsWith("access_token_cookie="));

    if (!tokenCookie) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const token = tokenCookie.split("=").slice(1).join("="); // handle '=' in JWT
    
    // Fix: use BACKEND_URL consistently (same as all other routes)
    const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:5000";
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);
    
    const flaskRes = await fetch(`${backendUrl}/api/v1/session/verify-behavior`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
      },
      body: rawBody,
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    const flaskData = await flaskRes.json();
    return NextResponse.json(flaskData, { status: flaskRes.status });

  } catch (error) {
    console.error("Behavioral verify error:", error);
    return NextResponse.json({ error: "Internal Server Error" }, { status: 500 });
  }
}

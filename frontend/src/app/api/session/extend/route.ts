import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { getBackendUrl } from "@/lib/backend-url";

export async function POST(req: Request) {
  try {
    const body = await req.json();

    const cookieStore = await cookies();
    const accessToken = cookieStore.get("access_token_cookie")?.value;

    if (!accessToken) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const backendUrl = getBackendUrl();

    // Forward behavioral data to the backend for re-evaluation
    const flaskRes = await fetch(`${backendUrl}/api/v1/session/extend`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${accessToken}`,
      },
      body: JSON.stringify(body),
    });

    const flaskData = await flaskRes.json();
    return NextResponse.json(flaskData, { status: flaskRes.status });
  } catch (error) {
    console.error("Session extend error:", error);
    return NextResponse.json({ error: "Extension failed" }, { status: 500 });
  }
}

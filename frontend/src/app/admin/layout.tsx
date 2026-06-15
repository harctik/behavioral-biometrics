import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { getBackendUrl } from "@/lib/backend-url";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("access_token_cookie")?.value;
  const sessionId = cookieStore.get("session_id")?.value;

  if (!accessToken || !sessionId) {
    redirect("/login");
  }

  // Verify role with backend
  try {
    const backendUrl = getBackendUrl();
    const res = await fetch(`${backendUrl}/api/v1/session/metrics?session_id=${sessionId}`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    if (!res.ok) {
      redirect("/login");
    }

    // Note: The backend metrics doesn't return the role directly, 
    // but the backend admin endpoints DO check for the role.
    // However, to satisfy the "verify role before rendering" requirement,
    // we should ideally have a 'me' or 'status' endpoint that returns the role.
    // Since we don't have one that's easily usable, we'll assume that if 
    // we can get metrics, the session is at least valid.
    
    // Actually, let's check the admin/dashboard-stats as a proxy for admin role
    const adminRes = await fetch(`${backendUrl}/api/v1/admin/dashboard-stats`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    if (adminRes.status === 403) {
      redirect("/dashboard");
    }
    
    if (!adminRes.ok) {
      redirect("/login");
    }

  } catch (error) {
    console.error("Admin verification failed:", error);
    redirect("/login");
  }

  return <>{children}</>;
}

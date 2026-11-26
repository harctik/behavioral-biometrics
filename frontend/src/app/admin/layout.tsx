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

  // The admin stats endpoint checks the role. redirect() works by throwing,
  // so choose the destination here and redirect outside the try block.
  let destination: string | null = null;
  try {
    const res = await fetch(`${getBackendUrl()}/api/v1/admin/dashboard-stats`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    if (res.status === 403) destination = "/dashboard";
    else if (!res.ok) destination = "/login";
  } catch (error) {
    console.error("Admin verification failed:", error);
    destination = "/login";
  }
  if (destination) redirect(destination);

  return <>{children}</>;
}

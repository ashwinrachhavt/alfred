import { cookies } from "next/headers";

import { AppShell } from "@/app/(app)/_components/app-shell";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const defaultSidebarOpen = cookieStore.get("sidebar_state")?.value !== "false";

  return <AppShell defaultSidebarOpen={defaultSidebarOpen}>{children}</AppShell>;
}

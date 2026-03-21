import { redirect } from "next/navigation";

import { auth } from "@clerk/nextjs/server";

import { AppShell } from "@/app/(app)/_components/app-shell";
import { isClerkEnabled } from "@/lib/auth";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  if (isClerkEnabled()) {
    const { userId } = await auth();
    if (!userId) {
      redirect("/sign-in");
    }
  }

  return <AppShell>{children}</AppShell>;
}

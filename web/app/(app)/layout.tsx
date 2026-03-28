import { AppShell } from "@/app/(app)/_components/app-shell";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // TODO: re-enable after Clerk keys refreshed
  // if (isClerkEnabled()) {
  //   const { userId } = await auth();
  //   if (!userId) {
  //     redirect("/sign-in");
  //   }
  // }

  return <AppShell>{children}</AppShell>;
}

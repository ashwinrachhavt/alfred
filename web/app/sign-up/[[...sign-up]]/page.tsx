import { redirect } from "next/navigation";

import { SignUp } from "@clerk/nextjs";

import { isClerkEnabled } from "@/lib/auth";
import { getAuth } from "@/lib/auth.server";

export default async function SignUpPage() {
  if (!isClerkEnabled()) {
    return (
      <main className="mx-auto flex min-h-dvh w-full max-w-6xl items-center justify-center px-4 py-10">
        <div className="bg-background text-foreground w-full max-w-md rounded-lg border p-6 shadow-sm">
          <h1 className="text-lg font-semibold tracking-tight">Authentication not configured</h1>
          <p className="text-muted-foreground mt-2 text-sm">
            Set{" "}
            <code className="bg-muted rounded px-1 py-0.5">NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code>{" "}
            to enable Clerk sign-up.
          </p>
        </div>
      </main>
    );
  }

  try {
    const { userId } = await getAuth();
    if (userId) {
      redirect("/inbox");
    }
  } catch {
    // Clerk middleware may not have run — fall through to the sign-up page.
  }

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-6xl items-center justify-center px-4 py-10">
      <SignUp />
    </main>
  );
}

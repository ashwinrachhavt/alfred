import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-6xl items-center justify-center px-4 py-10">
      <SignIn />
    </main>
  );
}


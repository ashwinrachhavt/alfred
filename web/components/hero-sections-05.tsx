import Link from "next/link";

import { SignedIn, SignedOut, SignInButton, SignUpButton } from "@clerk/nextjs";

import { Button } from "@/components/ui/button";
import { isClerkEnabled } from "@/lib/auth";

function ArcaneGrid() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      {/* Radial glow */}
      <div className="absolute top-1/2 left-1/2 h-[800px] w-[800px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,oklch(0.45_0.2_270/0.12)_0%,transparent_70%)]" />

      {/* Subtle grid lines */}
      <svg className="absolute inset-0 h-full w-full opacity-[0.04]" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="arcane-grid" width="64" height="64" patternUnits="userSpaceOnUse">
            <path d="M 64 0 L 0 0 0 64" fill="none" stroke="currentColor" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#arcane-grid)" />
      </svg>

      {/* Floating orbs */}
      <div className="arcane-float absolute top-[15%] left-[12%] h-1 w-1 rounded-full bg-indigo-400/40 shadow-[0_0_12px_4px_oklch(0.55_0.2_270/0.2)]" />
      <div className="arcane-float-delayed absolute top-[70%] right-[18%] h-1.5 w-1.5 rounded-full bg-violet-400/30 shadow-[0_0_16px_6px_oklch(0.5_0.22_290/0.15)]" />
      <div className="arcane-float-slow absolute top-[40%] right-[8%] h-0.5 w-0.5 rounded-full bg-indigo-300/50 shadow-[0_0_8px_3px_oklch(0.6_0.18_270/0.2)]" />
      <div className="arcane-float-delayed absolute bottom-[25%] left-[22%] h-1 w-1 rounded-full bg-purple-400/25 shadow-[0_0_10px_4px_oklch(0.5_0.2_300/0.12)]" />
    </div>
  );
}

function Sigil() {
  return (
    <div className="relative mx-auto mb-10 flex h-20 w-20 items-center justify-center">
      {/* Outer ring */}
      <div className="absolute inset-0 rounded-full border border-indigo-500/20" />
      <div className="arcane-spin absolute inset-[-4px] rounded-full border border-dashed border-violet-400/10" />
      {/* Inner glow */}
      <div className="absolute inset-2 rounded-full bg-[radial-gradient(circle,oklch(0.5_0.22_270/0.15)_0%,transparent_70%)]" />
      {/* Letter */}
      <span className="relative text-3xl font-light tracking-wide text-indigo-300/90 select-none">
        A
      </span>
    </div>
  );
}

export default function HeroSection() {
  const clerkEnabled = isClerkEnabled();

  return (
    <section className="relative flex min-h-[92vh] flex-col items-center justify-center overflow-hidden px-4 py-20">
      <ArcaneGrid />

      <div className="relative z-10 mx-auto max-w-2xl text-center">
        <Sigil />

        {/* Title */}
        <h1 className="text-5xl font-semibold tracking-tight sm:text-6xl lg:text-7xl">
          <span className="bg-gradient-to-b from-white to-white/60 bg-clip-text text-transparent">
            Alfred
          </span>
        </h1>

        {/* One-liner */}
        <p className="mx-auto mt-6 max-w-md text-lg leading-relaxed font-light tracking-wide text-indigo-200/60">
          The things you know, sharpened.
        </p>

        {/* Subtle descriptor */}
        <p className="text-muted-foreground mx-auto mt-4 max-w-lg text-sm leading-relaxed">
          A knowledge workbench that captures, distills, and connects everything
          you learn — so nothing slips through the cracks.
        </p>

        {/* CTA */}
        <div className="mt-10 flex items-center justify-center gap-4">
          {clerkEnabled ? (
            <>
              <SignedOut>
                <SignInButton mode="modal">
                  <Button
                    size="lg"
                    className="rounded-full border border-indigo-500/20 bg-indigo-600/90 px-8 text-white shadow-[0_0_24px_-4px_oklch(0.5_0.22_270/0.4)] hover:bg-indigo-500/90 hover:shadow-[0_0_32px_-2px_oklch(0.5_0.22_270/0.5)]"
                  >
                    Enter
                  </Button>
                </SignInButton>
                <SignUpButton mode="modal">
                  <Button
                    size="lg"
                    variant="ghost"
                    className="text-muted-foreground rounded-full px-8 hover:text-white"
                  >
                    Create account
                  </Button>
                </SignUpButton>
              </SignedOut>
              <SignedIn>
                <Button
                  asChild
                  size="lg"
                  className="rounded-full border border-indigo-500/20 bg-indigo-600/90 px-8 text-white shadow-[0_0_24px_-4px_oklch(0.5_0.22_270/0.4)] hover:bg-indigo-500/90 hover:shadow-[0_0_32px_-2px_oklch(0.5_0.22_270/0.5)]"
                >
                  <Link href="/dashboard">Enter the workbench</Link>
                </Button>
              </SignedIn>
            </>
          ) : (
            <Button
              asChild
              size="lg"
              className="rounded-full border border-indigo-500/20 bg-indigo-600/90 px-8 text-white shadow-[0_0_24px_-4px_oklch(0.5_0.22_270/0.4)] hover:bg-indigo-500/90 hover:shadow-[0_0_32px_-2px_oklch(0.5_0.22_270/0.5)]"
            >
              <Link href="/dashboard">Enter the workbench</Link>
            </Button>
          )}
        </div>

        {/* Bottom accent line */}
        <div className="mx-auto mt-16 h-px w-32 bg-gradient-to-r from-transparent via-indigo-500/30 to-transparent" />
      </div>
    </section>
  );
}

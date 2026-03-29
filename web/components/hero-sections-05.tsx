import Link from "next/link";

import { SignedIn, SignedOut, SignInButton, SignUpButton } from "@clerk/nextjs";

import { Button } from "@/components/ui/button";
import { isClerkEnabled } from "@/lib/auth";

export default function HeroSection() {
 const clerkEnabled = isClerkEnabled();

 return (
 <section className="relative flex min-h-[92vh] flex-col items-center justify-center overflow-hidden px-4 py-20">
 {/* Subtle grid background */}
 <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
 <svg className="absolute inset-0 h-full w-full opacity-[0.03]" xmlns="http://www.w3.org/2000/svg">
 <defs>
 <pattern id="alfred-grid" width="64" height="64" patternUnits="userSpaceOnUse">
 <path d="M 64 0 L 0 0 0 64" fill="none" stroke="currentColor" strokeWidth="0.5" />
 </pattern>
 </defs>
 <rect width="100%" height="100%" fill="url(#alfred-grid)" />
 </svg>
 </div>

 <div className="relative z-10 mx-auto max-w-2xl text-center">
 {/* Overline */}
 <div className="mb-8 flex items-center justify-center gap-3">
 <div className="h-px w-8 bg-primary" />
 <span className="text-[11px] uppercase tracking-[0.15em] text-primary">
 Knowledge Factory
 </span>
 <div className="h-px w-8 bg-primary" />
 </div>

 {/* Title — Inter (sans) */}
 <h1 className="text-6xl tracking-tight sm:text-7xl lg:text-8xl">
 Alfred<span className="text-primary">.</span>
 </h1>

 {/* Tagline */}
 <p className="mx-auto mt-6 max-w-md text-lg font-light leading-relaxed text-muted-foreground">
 The things you know, sharpened.
 </p>

 {/* Description */}
 <p className="mx-auto mt-4 max-w-lg text-sm leading-relaxed text-[var(--alfred-text-tertiary)]">
 A knowledge workbench that captures, distills, and connects everything
 you learn — so nothing slips through the cracks.
 </p>

 {/* CTA */}
 <div className="mt-10 flex items-center justify-center gap-4">
 {clerkEnabled ? (
 <>
 <SignedOut>
 <SignInButton mode="modal">
 <Button size="lg" className="text-sm tracking-wide">
 Begin Thinking
 </Button>
 </SignInButton>
 <SignUpButton mode="modal">
 <Button size="lg" variant="outline" className="text-sm tracking-wide">
 Create account
 </Button>
 </SignUpButton>
 </SignedOut>
 <SignedIn>
 <Button asChild size="lg" className="text-sm tracking-wide">
 <Link href="/inbox">Enter the workbench</Link>
 </Button>
 </SignedIn>
 </>
 ) : (
 <Button asChild size="lg" className="text-sm tracking-wide">
 <Link href="/inbox">Begin Thinking</Link>
 </Button>
 )}
 </div>

 {/* Bottom accent line */}
 <div className="mx-auto mt-16 h-px w-32 bg-gradient-to-r from-transparent via-primary/40 to-transparent" />
 </div>
 </section>
 );
}

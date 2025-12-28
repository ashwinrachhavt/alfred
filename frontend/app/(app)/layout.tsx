import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-50 border-b bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-3">
            <Link href="/" className="font-semibold tracking-tight">
              Alfred
            </Link>
            <span className="hidden text-xs text-muted-foreground sm:inline">
              Knowledge workbench
            </span>
          </div>
          <nav className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link href="/system-design">System Design</Link>
            </Button>
            <Button asChild variant="ghost" size="sm">
              <Link href="/interview-prep">Interview Prep</Link>
            </Button>
          </nav>
        </div>
      </header>

      <main>{children}</main>
    </div>
  );
}


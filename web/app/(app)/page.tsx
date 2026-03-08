import Image from "next/image";
import Link from "next/link";
import { redirect } from "next/navigation";

import { auth } from "@clerk/nextjs/server";

import HeroSection from "@/components/hero-sections-05";
import { Page } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { isClerkEnabled } from "@/lib/auth";

export default async function Home() {
  if (isClerkEnabled()) {
    const { userId } = await auth();
    if (userId) {
      redirect("/dashboard");
    }
  }

  return (
    <>
      <HeroSection />
      <Page size="wide" className="pt-0 pb-14">
        <div className="space-y-14">
          <section className="grid gap-6 lg:grid-cols-12 lg:items-start">
            <div className="space-y-2 lg:col-span-5">
              <h2 className="text-2xl font-semibold tracking-tight">Start where your work is.</h2>
              <p className="text-muted-foreground">
                Keep a clean surface area. Each workflow keeps its own timeline and history.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:col-span-7">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Company Intelligence</CardTitle>
                </CardHeader>
                <CardContent className="text-muted-foreground space-y-3 text-sm">
                  Generate concise research briefs with citations and revisit them when you need to
                  refresh context.
                  <div>
                    <Button asChild size="sm" variant="outline">
                      <Link href="/company">Open Company</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Library</CardTitle>
                </CardHeader>
                <CardContent className="text-muted-foreground space-y-3 text-sm">
                  Build a knowledge base and keep your notes searchable and structured.
                  <div>
                    <Button asChild size="sm" variant="outline">
                      <Link href="/library">Open Library</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">System Design</CardTitle>
                </CardHeader>
                <CardContent className="text-muted-foreground space-y-3 text-sm">
                  Design systems visually with diagrams, notes, and AI-assisted architecture reviews.
                  <div>
                    <Button asChild size="sm" variant="outline">
                      <Link href="/system-design">Open System Design</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Interview Prep</CardTitle>
                </CardHeader>
                <CardContent className="text-muted-foreground space-y-3 text-sm">
                  Practice with drills and get AI feedback to sharpen your interview skills.
                  <div>
                    <Button asChild size="sm" variant="outline">
                      <Link href="/interview-prep">Open Interview Prep</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </section>

          <section className="grid gap-8 lg:grid-cols-12 lg:items-center">
            <div className="space-y-4 lg:col-span-5">
              <h2 className="text-2xl font-semibold tracking-tight">
                Focused modes when you need them.
              </h2>
              <p className="text-muted-foreground">
                System Design and Interview Prep live as dedicated workbenches — built for deep
                work, not constant navigation.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button asChild variant="outline">
                  <Link href="/system-design">Open System Design</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href="/interview-prep">Open Interview Prep</Link>
                </Button>
              </div>
            </div>

            <div className="lg:col-span-7">
              <div className="bg-background/70 overflow-hidden rounded-3xl border p-4 shadow-sm backdrop-blur">
                <Image
                  src="/landing/blueprint-light.svg"
                  alt="System blueprint illustration"
                  width={1200}
                  height={900}
                  className="block h-auto w-full dark:hidden"
                  loading="lazy"
                />
                <Image
                  src="/landing/blueprint-dark.svg"
                  alt="System blueprint illustration"
                  width={1200}
                  height={900}
                  className="hidden h-auto w-full dark:block"
                  loading="lazy"
                />
              </div>
            </div>
          </section>
        </div>
      </Page>
    </>
  );
}

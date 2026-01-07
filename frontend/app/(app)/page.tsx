import Image from "next/image";
import Link from "next/link";

import { Page } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <Page size="wide" className="py-14">
      <div className="space-y-14">
        <section className="bg-muted/10 relative overflow-hidden rounded-3xl border">
          <div className="absolute inset-0 -z-10 bg-gradient-to-br from-primary/10 via-transparent to-secondary/10" />

          <div className="grid gap-10 p-8 lg:grid-cols-[1fr_520px] lg:items-center">
            <div className="space-y-5">
              <p className="text-muted-foreground text-sm font-medium tracking-wide">
                Second brain, not second tab.
              </p>
              <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
                A calm workspace for thinking.
              </h1>
              <p className="text-muted-foreground max-w-xl text-lg">
                Alfred turns scattered notes, research, and practice into durable knowledge — with
                context preserved.
              </p>
              <div className="flex flex-wrap gap-3">
                <Button asChild>
                  <Link href="/company">Research a company</Link>
                </Button>
                <Button asChild variant="outline">
                  <Link href="/documents">Browse documents</Link>
                </Button>
                <Button asChild variant="ghost">
                  <Link href="/rag">Ask Alfred</Link>
                </Button>
              </div>
              <div className="text-muted-foreground flex flex-wrap gap-2 text-xs">
                <span className="bg-background/60 rounded-full border px-3 py-1">Citations</span>
                <span className="bg-background/60 rounded-full border px-3 py-1">
                  Long-running tasks
                </span>
                <span className="bg-background/60 rounded-full border px-3 py-1">
                  Focused workflows
                </span>
              </div>
            </div>

            <div className="relative">
              <div className="absolute -inset-6 -z-10 rounded-3xl bg-gradient-to-br from-primary/20 via-transparent to-secondary/20 blur-2xl" />
              <div className="bg-background/70 overflow-hidden rounded-3xl border p-4 shadow-sm backdrop-blur">
                <Image
                  src="/landing/knowledge-graph-light.svg"
                  alt="Knowledge graph illustration"
                  width={1200}
                  height={900}
                  className="block h-auto w-full dark:hidden"
                  priority
                />
                <Image
                  src="/landing/knowledge-graph-dark.svg"
                  alt="Knowledge graph illustration"
                  width={1200}
                  height={900}
                  className="hidden h-auto w-full dark:block"
                  priority
                />
              </div>
            </div>
          </div>
        </section>

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
                <CardTitle className="text-base">Documents</CardTitle>
              </CardHeader>
              <CardContent className="text-muted-foreground space-y-3 text-sm">
                Build a knowledge base and keep your notes searchable and structured.
                <div>
                  <Button asChild size="sm" variant="outline">
                    <Link href="/documents">Open Documents</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Knowledge Assistant</CardTitle>
              </CardHeader>
              <CardContent className="text-muted-foreground space-y-3 text-sm">
                Ask questions across your documents and get answers with citations.
                <div>
                  <Button asChild size="sm" variant="outline">
                    <Link href="/rag">Open Assistant</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Tasks</CardTitle>
              </CardHeader>
              <CardContent className="text-muted-foreground space-y-3 text-sm">
                Track long-running jobs and jump back to results without losing your place.
                <div>
                  <Button asChild size="sm" variant="outline">
                    <Link href="/tasks">Open Tasks</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </section>

        <section className="grid gap-8 lg:grid-cols-12 lg:items-center">
          <div className="space-y-4 lg:col-span-5">
            <h2 className="text-2xl font-semibold tracking-tight">Focused modes when you need them.</h2>
            <p className="text-muted-foreground">
              System Design and Interview Prep live as dedicated workbenches — built for deep work,
              not constant navigation.
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
  );
}

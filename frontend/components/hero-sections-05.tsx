import Image from "next/image";
import Link from "next/link";

import { Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function HeroSection() {
  return (
    <section className="mx-auto w-full max-w-7xl px-4 py-14 lg:py-20">
      <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-2">
        <div className="space-y-8">
          <Badge variant="outline" className="inline-flex items-center gap-2 rounded-full px-2 py-1">
            <Sparkles className="size-4" />
            Second brain, not second tab.
          </Badge>

          <div className="mx-auto max-w-xl space-y-6 text-center lg:mx-0 lg:text-start">
            <h1 className="text-5xl font-semibold tracking-tight lg:text-6xl">
              A calm workspace for <span className="text-muted-foreground italic">thinking</span>.
            </h1>

            <p className="text-muted-foreground text-lg leading-relaxed">
              Alfred turns scattered notes, research, and practice into durable knowledge — with context preserved.
            </p>
          </div>

          <div className="flex justify-center gap-4 lg:justify-start">
            <Button asChild size="lg" className="rounded-full">
              <Link href="/company">Research a company</Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="rounded-full">
              <Link href="/rag">Ask Alfred</Link>
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6">
          <div className="space-y-6">
            <Card className="mt-8 overflow-hidden border-none p-0 shadow-none">
              <div className="relative aspect-[4/3] w-full">
                <Image
                  src="/landing/knowledge-graph-light.svg"
                  alt="Knowledge graph illustration"
                  fill
                  sizes="(min-width: 1024px) 520px, 100vw"
                  className="object-cover dark:hidden"
                  priority
                />
                <Image
                  src="/landing/knowledge-graph-dark.svg"
                  alt="Knowledge graph illustration"
                  fill
                  sizes="(min-width: 1024px) 520px, 100vw"
                  className="hidden object-cover dark:block"
                  priority
                />
              </div>
            </Card>

            <Card className="bg-muted aspect-[4/3] border-none shadow-none">
              <CardContent className="flex h-full flex-col justify-end">
                <div>
                  <div className="mb-2 text-3xl font-medium tracking-tight sm:text-4xl">Citations</div>
                  <div className="text-muted-foreground">Know where every claim comes from.</div>
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="-mb-8 space-y-6">
            <Card className="bg-muted aspect-[4/3] border-none shadow-none">
              <CardContent className="flex h-full flex-col justify-end">
                <div>
                  <div className="mb-2 text-3xl font-medium tracking-tight sm:text-4xl">Tasks</div>
                  <div className="text-muted-foreground">
                    Track long-running jobs and return to results.
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="aspect-[4/3] border-none bg-amber-50 shadow-none dark:bg-amber-950">
              <CardContent className="flex h-full flex-col justify-end">
                <div className="mb-2 text-3xl font-medium tracking-tight sm:text-4xl">Workbenches</div>
                <div className="text-muted-foreground mb-4">Deep work modes when you need them.</div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">Company</Badge>
                  <Badge variant="secondary">Documents</Badge>
                  <Badge variant="secondary">Assistant</Badge>
                  <Badge variant="secondary">System Design</Badge>
                  <Badge variant="secondary">Interview Prep</Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </section>
  );
}


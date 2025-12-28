import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-14">
      <div className="grid gap-10 lg:grid-cols-[1fr_380px]">
        <div className="space-y-5">
          <h1 className="text-4xl font-semibold tracking-tight">
            A calm, powerful workspace for thinking.
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground">
            Alfred helps you practice interviews and turn messy information into durable knowledge.
            Start with System Design or Interview Prep.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button asChild>
              <Link href="/system-design">Start System Design</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/interview-prep">Open Interview Prep</Link>
            </Button>
          </div>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>What you can do</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="rounded-lg border bg-background p-3">
              <p className="font-medium">System Design whiteboard</p>
              <p className="text-xs text-muted-foreground">
                Draw your architecture and get probing questions, critiques, and a publishable
                knowledge draft.
              </p>
            </div>
            <div className="rounded-lg border bg-background p-3">
              <p className="font-medium">Interview Prep workflows</p>
              <p className="text-xs text-muted-foreground">
                Collect questions, research the company, and run practice sessions.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

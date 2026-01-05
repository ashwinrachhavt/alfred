import Link from "next/link";

import { Page } from "@/components/layout/page";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <Page className="py-14">
      <div className="grid gap-10 lg:grid-cols-[1fr_380px]">
        <div className="space-y-5">
          <h1 className="text-4xl font-semibold tracking-tight">
            A calm, powerful workspace for thinking.
          </h1>
          <p className="text-muted-foreground max-w-2xl text-lg">
            Alfred helps you practice interviews and turn messy information into durable knowledge.
            Start with System Design, Interview Prep, or your knowledge base.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button asChild>
              <Link href="/system-design">Start System Design</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/interview-prep">Open Interview Prep</Link>
            </Button>
            <Button asChild variant="ghost">
              <Link href="/documents">Browse Documents</Link>
            </Button>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Company Intelligence</CardTitle>
              </CardHeader>
              <CardContent className="text-muted-foreground space-y-3 text-sm">
                Search, research, and track your target companies.
                <div>
                  <Button asChild size="sm" variant="outline">
                    <Link href="/company">Open</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Knowledge Assistant</CardTitle>
              </CardHeader>
              <CardContent className="text-muted-foreground space-y-3 text-sm">
                Ask questions across your documents with citations.
                <div>
                  <Button asChild size="sm" variant="outline">
                    <Link href="/rag">Open</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Calendar & Email</CardTitle>
              </CardHeader>
              <CardContent className="text-muted-foreground space-y-3 text-sm">
                Connect Google and run scheduling workflows.
                <div>
                  <Button asChild size="sm" variant="outline">
                    <Link href="/calendar">Open</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Background Tasks</CardTitle>
              </CardHeader>
              <CardContent className="text-muted-foreground space-y-3 text-sm">
                Monitor long-running jobs and their results.
                <div>
                  <Button asChild size="sm" variant="outline">
                    <Link href="/tasks">Open</Link>
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>What you can do</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="bg-background rounded-lg border p-3">
              <p className="font-medium">System Design whiteboard</p>
              <p className="text-muted-foreground text-xs">
                Draw your architecture and get probing questions, critiques, and a publishable
                knowledge draft.
              </p>
            </div>
            <div className="bg-background rounded-lg border p-3">
              <p className="font-medium">Interview Prep workflows</p>
              <p className="text-muted-foreground text-xs">
                Collect questions, research the company, and run practice sessions.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </Page>
  );
}

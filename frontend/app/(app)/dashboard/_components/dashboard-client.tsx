"use client";

import Link from "next/link";
import * as React from "react";

import { useRecentCompanyResearchReports } from "@/features/company/queries";
import { useRecentDocuments } from "@/features/documents/queries";
import { useThreads } from "@/features/threads/queries";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function formatTimestamp(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return null;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(date);
}

export function DashboardClient() {
  const recentDocuments = useRecentDocuments(6);
  const recentReports = useRecentCompanyResearchReports(6);
  const threads = useThreads();

  const sortedThreads = React.useMemo(() => {
    const items = threads.data ?? [];

    return items
      .slice()
      .sort((a, b) => {
        const aTime = a.updated_at
          ? Date.parse(a.updated_at)
          : a.created_at
            ? Date.parse(a.created_at)
            : 0;
        const bTime = b.updated_at
          ? Date.parse(b.updated_at)
          : b.created_at
            ? Date.parse(b.created_at)
            : 0;
        return bTime - aTime;
      })
      .slice(0, 6);
  }, [threads.data]);

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground text-sm">
            Jump back into recent work and start a new session quickly.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button asChild size="sm">
            <Link href="/company">Research a company</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/rag">Ask Alfred</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/documents">Documents</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/tasks">Tasks</Link>
          </Button>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader className="space-y-1">
            <CardTitle className="text-base">Recent documents</CardTitle>
            <p className="text-muted-foreground text-sm">Your latest notes and captures.</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {recentDocuments.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-5 w-3/4" />
                <Skeleton className="h-5 w-5/6" />
                <Skeleton className="h-5 w-2/3" />
              </div>
            ) : recentDocuments.isError ? (
              <div className="space-y-2">
                <p className="text-muted-foreground text-sm">
                  Couldn&apos;t load documents. Is the API running?
                </p>
                <Button size="sm" variant="outline" onClick={() => void recentDocuments.refetch()}>
                  Retry
                </Button>
              </div>
            ) : recentDocuments.data?.items?.length ? (
              <ul className="space-y-2">
                {recentDocuments.data.items.slice(0, 6).map((doc) => (
                  <li key={doc.id} className="flex items-start justify-between gap-3">
                    <Link
                      href={`/documents/${doc.id}`}
                      className="hover:text-foreground text-sm leading-snug font-medium underline-offset-4 hover:underline"
                    >
                      {doc.title || "Untitled document"}
                    </Link>
                    <div className="text-muted-foreground shrink-0 text-xs">
                      {formatTimestamp(doc.created_at) ?? doc.day_bucket}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground text-sm">No documents yet.</p>
            )}

            <div>
              <Button asChild size="sm" variant="ghost">
                <Link href="/documents">Browse documents</Link>
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="space-y-1">
            <CardTitle className="text-base">Company research</CardTitle>
            <p className="text-muted-foreground text-sm">Recent briefs and executive summaries.</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {recentReports.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-5 w-4/5" />
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-5 w-3/4" />
              </div>
            ) : recentReports.isError ? (
              <div className="space-y-2">
                <p className="text-muted-foreground text-sm">
                  Couldn&apos;t load reports. Is the API running?
                </p>
                <Button size="sm" variant="outline" onClick={() => void recentReports.refetch()}>
                  Retry
                </Button>
              </div>
            ) : recentReports.data?.length ? (
              <ul className="space-y-2">
                {recentReports.data.slice(0, 6).map((report) => (
                  <li key={report.id} className="space-y-1">
                    <div className="flex items-start justify-between gap-3">
                      <Link
                        href={`/company?reportId=${encodeURIComponent(report.id)}`}
                        className="hover:text-foreground text-sm leading-snug font-medium underline-offset-4 hover:underline"
                      >
                        {report.company}
                      </Link>
                      <div className="text-muted-foreground shrink-0 text-xs">
                        {formatTimestamp(report.updated_at ?? report.generated_at)}
                      </div>
                    </div>
                    {report.executive_summary ? (
                      <p className="text-muted-foreground line-clamp-2 text-sm">
                        {report.executive_summary}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground text-sm">No company reports yet.</p>
            )}

            <div className="flex flex-wrap gap-2">
              <Button asChild size="sm" variant="ghost">
                <Link href="/company">Open company research</Link>
              </Button>
              <Badge variant="secondary">Citations</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="space-y-1">
            <CardTitle className="text-base">Threads</CardTitle>
            <p className="text-muted-foreground text-sm">Recent conversations and notes.</p>
          </CardHeader>
          <CardContent className="space-y-3">
            {threads.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-5 w-2/3" />
                <Skeleton className="h-5 w-5/6" />
                <Skeleton className="h-5 w-3/5" />
              </div>
            ) : threads.isError ? (
              <div className="space-y-2">
                <p className="text-muted-foreground text-sm">
                  Couldn&apos;t load threads. Is the API running?
                </p>
                <Button size="sm" variant="outline" onClick={() => void threads.refetch()}>
                  Retry
                </Button>
              </div>
            ) : sortedThreads.length ? (
              <ul className="space-y-2">
                {sortedThreads.map((thread) => (
                  <li key={thread.id} className="flex items-start justify-between gap-3">
                    <Link
                      href={`/threads/${thread.id}`}
                      className="hover:text-foreground text-sm leading-snug font-medium underline-offset-4 hover:underline"
                    >
                      {thread.title || thread.kind || "Untitled thread"}
                    </Link>
                    <div className="text-muted-foreground shrink-0 text-xs">
                      {formatTimestamp(thread.updated_at ?? thread.created_at)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-muted-foreground text-sm">No threads yet.</p>
            )}

            <div>
              <Button asChild size="sm" variant="ghost">
                <Link href="/threads">Open threads</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

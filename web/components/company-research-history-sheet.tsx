"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Clock, ExternalLink } from "lucide-react";

import { formatRelativeTimestamp } from "@/lib/utils/date-format";
import { useRecentCompanyResearchReports } from "@/features/company/queries";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";

type CompanyResearchHistorySheetProps = {
  trigger?: React.ReactElement;
};

export function CompanyResearchHistorySheet({ trigger }: CompanyResearchHistorySheetProps) {
  const router = useRouter();
  const recent = useRecentCompanyResearchReports(20);

  return (
    <Sheet>
      <SheetTrigger asChild>
        {trigger ?? (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Open recent company research"
          >
            <Clock className="h-4 w-4" />
          </Button>
        )}
      </SheetTrigger>

      <SheetContent side="right" className="w-[420px] sm:max-w-[420px]">
        <SheetHeader>
          <SheetTitle>Recent research</SheetTitle>
        </SheetHeader>

        <div className="flex-1 overflow-auto">
          {recent.isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, idx) => (
                <div key={idx} className="bg-background space-y-2 rounded-lg border p-3">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-3/4" />
                </div>
              ))}
            </div>
          ) : null}

          {recent.error ? (
            <Alert variant="destructive" className="mt-3">
              <AlertDescription className="text-destructive">
                {recent.error instanceof Error ? recent.error.message : "Failed to load."}
              </AlertDescription>
            </Alert>
          ) : null}

          {recent.data?.length ? (
            <div className="space-y-3">
              {recent.data.map((item) => (
                <div key={item.id} className="bg-background rounded-lg border p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="truncate text-sm font-medium">{item.company}</p>
                        <span className="text-muted-foreground text-xs">
                          {formatRelativeTimestamp(item.updated_at ?? item.generated_at)}
                        </span>
                      </div>
                      {item.executive_summary ? (
                        <p className="text-muted-foreground mt-1 line-clamp-3 text-xs">
                          {item.executive_summary}
                        </p>
                      ) : null}
                    </div>

                    <div className="flex shrink-0 items-center gap-1">
                      <SheetClose asChild>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            router.push(`/company?reportId=${encodeURIComponent(item.id)}`)
                          }
                        >
                          Open
                        </Button>
                      </SheetClose>
                      <Button
                        asChild
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label="Open company page"
                      >
                        <Link href="/company">
                          <ExternalLink className="h-4 w-4" />
                        </Link>
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : recent.isLoading || recent.error ? null : (
            <EmptyState
              title="No research yet"
              description="Generate your first company research report to see it here."
              action={
                <SheetClose asChild>
                  <Button asChild type="button" variant="outline" size="sm">
                    <Link href="/company">Open Company</Link>
                  </Button>
                </SheetClose>
              }
            />
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

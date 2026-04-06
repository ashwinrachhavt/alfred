import { Skeleton } from "@/components/ui/skeleton";

export function DictionaryEntrySkeleton() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Skeleton className="h-10 w-48" />
        <Skeleton className="mt-2 h-4 w-32" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-4 w-full" />
      </div>
      <Skeleton className="h-8 w-24" />
      <Skeleton className="h-32 w-full rounded-lg" />
    </div>
  );
}

import { Skeleton } from "@/components/ui/skeleton";

export default function KnowledgeLoading() {
  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="px-6 pt-6 pb-4">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="mt-1 h-4 w-64" />
      </div>

      {/* View toolbar */}
      <div className="border-b px-6 py-3">
        <div className="flex items-center gap-4">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-8 w-32" />
          <Skeleton className="ml-auto h-8 w-64" />
        </div>
      </div>

      {/* Filter bar */}
      <div className="border-b px-6 py-3">
        <div className="flex gap-2">
          <Skeleton className="h-8 w-28" />
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-8 w-32" />
        </div>
      </div>

      {/* Content - 3x3 grid of cards */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="flex flex-col rounded-lg border p-4 space-y-3">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
              <div className="flex gap-2 pt-1">
                <Skeleton className="h-5 w-16 rounded-sm" />
                <Skeleton className="h-5 w-12 rounded-sm" />
                <Skeleton className="ml-auto h-5 w-8" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

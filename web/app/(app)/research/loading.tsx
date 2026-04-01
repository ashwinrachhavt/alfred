import { Skeleton } from "@/components/ui/skeleton";

export default function ResearchLoading() {
  return (
    <div className="flex h-full">
      <div className="w-[280px] space-y-3 border-r p-4">
        <Skeleton className="h-8 w-full" />
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-lg" />
        ))}
      </div>
      <div className="flex-1 space-y-4 p-6">
        <Skeleton className="h-8 w-96" />
        <Skeleton className="h-32 w-full rounded-lg" />
        <div className="grid grid-cols-3 gap-4">
          <Skeleton className="h-24 rounded-lg" />
          <Skeleton className="h-24 rounded-lg" />
          <Skeleton className="h-24 rounded-lg" />
        </div>
      </div>
    </div>
  );
}

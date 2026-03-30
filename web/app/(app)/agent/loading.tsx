import { Skeleton } from "@/components/ui/skeleton";

export default function AgentLoading() {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col p-6">
      <Skeleton className="mb-6 h-8 w-48" />
      <div className="flex-1 space-y-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-20 w-full rounded-lg" />
        ))}
      </div>
      <Skeleton className="mt-4 h-24 w-full rounded-lg" />
    </div>
  );
}

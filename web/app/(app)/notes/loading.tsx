import { Skeleton } from "@/components/ui/skeleton";

export default function NotesLoading() {
  return (
    <div className="flex h-full">
      <div className="w-64 space-y-2 border-r p-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full rounded" />
        ))}
      </div>
      <div className="flex-1 p-8">
        <Skeleton className="mb-4 h-10 w-96" />
        <Skeleton className="h-[60vh] w-full rounded-lg" />
      </div>
    </div>
  );
}

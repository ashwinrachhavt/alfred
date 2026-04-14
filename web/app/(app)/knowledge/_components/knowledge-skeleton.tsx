export function KnowledgeSkeleton() {
  return (
    <div className="p-6">
      <div className="mb-6 flex gap-3">
        <div className="h-9 w-32 animate-pulse rounded-md bg-muted" />
        <div className="h-9 w-32 animate-pulse rounded-md bg-muted" />
        <div className="ml-auto h-9 w-48 animate-pulse rounded-md bg-muted" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="h-36 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    </div>
  );
}

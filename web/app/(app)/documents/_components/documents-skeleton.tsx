export function DocumentsSkeleton() {
  return (
    <div className="p-6">
      <div className="mb-6 flex gap-3">
        <div className="h-9 w-40 animate-pulse rounded-md bg-muted" />
        <div className="ml-auto h-9 w-48 animate-pulse rounded-md bg-muted" />
      </div>
      <div className="space-y-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="h-12 w-12 animate-pulse rounded-md bg-muted" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
              <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

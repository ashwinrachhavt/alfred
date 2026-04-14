export function NotesSkeleton() {
  return (
    <div className="flex h-full">
      <div className="w-64 space-y-2 border-r p-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
      <div className="flex-1 p-8">
        <div className="mb-4 h-8 w-64 animate-pulse rounded-md bg-muted" />
        <div className="space-y-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className="h-4 animate-pulse rounded bg-muted"
              style={{ width: `${60 + Math.random() * 40}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

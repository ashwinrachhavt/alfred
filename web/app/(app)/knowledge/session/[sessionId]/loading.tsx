/**
 * Skeleton for the workspace shell. Mirrors the three-zone layout
 * (header / rail / writing surface / ambient panel) at rest.
 */
export default function WorkspaceSessionLoading() {
  return (
    <div className="flex min-h-screen flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--alfred-ruled-line)] px-6 py-3">
        <div className="h-4 w-40 rounded bg-muted/40 animate-pulse" />
        <div className="h-5 w-56 rounded bg-muted/40 animate-pulse" />
        <div className="h-7 w-24 rounded bg-muted/40 animate-pulse" />
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Rail */}
        <div className="w-60 shrink-0 border-r border-[var(--alfred-ruled-line)] px-5 py-4">
          <div className="h-3 w-24 rounded bg-muted/40 animate-pulse" />
          <div className="mt-6 space-y-3">
            <div className="h-10 w-full rounded bg-muted/40 animate-pulse" />
            <div className="h-10 w-full rounded bg-muted/40 animate-pulse" />
            <div className="h-10 w-full rounded bg-muted/40 animate-pulse" />
          </div>
        </div>

        {/* Writing surface */}
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[720px] px-8 py-10">
            <div className="h-10 w-2/3 rounded bg-muted/40 animate-pulse" />
            <div className="mt-6 space-y-3">
              <div className="h-4 w-full rounded bg-muted/40 animate-pulse" />
              <div className="h-4 w-5/6 rounded bg-muted/40 animate-pulse" />
              <div className="h-4 w-4/5 rounded bg-muted/40 animate-pulse" />
              <div className="h-4 w-3/4 rounded bg-muted/40 animate-pulse" />
            </div>
          </div>
        </div>

        {/* Ambient panel */}
        <div className="w-80 shrink-0 border-l border-[var(--alfred-ruled-line)] px-5 py-5">
          <div className="h-3 w-32 rounded bg-muted/40 animate-pulse" />
          <div className="mt-4 h-16 w-full rounded bg-muted/40 animate-pulse" />
          <div className="mt-6 h-3 w-28 rounded bg-muted/40 animate-pulse" />
          <div className="mt-3 space-y-2">
            <div className="h-4 w-full rounded bg-muted/40 animate-pulse" />
            <div className="h-4 w-5/6 rounded bg-muted/40 animate-pulse" />
            <div className="h-4 w-3/4 rounded bg-muted/40 animate-pulse" />
          </div>
        </div>
      </div>
    </div>
  );
}

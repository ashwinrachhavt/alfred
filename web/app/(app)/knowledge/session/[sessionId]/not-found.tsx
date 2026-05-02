import Link from "next/link";

export default function WorkspaceSessionNotFound() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-6 text-center">
      <h1 className="font-serif text-[28px] leading-[1.2] text-foreground">
        Session not found
      </h1>
      <p className="mt-3 font-mono text-[10px] uppercase tracking-wider text-[var(--alfred-text-tertiary)]">
        This sitting has ended, been archived, or never existed.
      </p>
      <Link
        href="/knowledge/session/new"
        className="mt-8 rounded bg-primary px-4 py-2 font-mono text-[10px] font-medium uppercase tracking-wider text-primary-foreground transition-opacity hover:opacity-90"
      >
        Start a new sitting
      </Link>
    </div>
  );
}

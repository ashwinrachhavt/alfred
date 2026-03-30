import { Settings } from "lucide-react";

export const metadata = { title: "Settings — Alfred" };

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8 px-6 py-8">
      <div>
        <h1 className="font-serif text-3xl tracking-tight">Settings</h1>
        <p className="mt-1 font-mono text-xs uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          Configure your knowledge factory
        </p>
      </div>

      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-[var(--border)] py-16">
        <Settings className="size-10 text-muted-foreground/40" />
        <p className="mt-4 font-mono text-sm text-muted-foreground">
          Settings coming soon
        </p>
        <p className="mt-1 text-xs text-[var(--alfred-text-tertiary)]">
          Theme and accent preferences are available via the palette icon in the header.
        </p>
      </div>
    </div>
  );
}

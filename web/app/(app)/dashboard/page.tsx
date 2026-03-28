import { LiveKnowledgeScore } from "./_components/live-knowledge-score";
import { RetentionCard } from "./_components/retention-card";
import { CoverageCard } from "./_components/coverage-card";
import { ConnectionsCard } from "./_components/connections-card";
import { ActivityStrip } from "./_components/activity-strip";

export const metadata = { title: "Dashboard — Alfred" };

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-8 px-6 py-8">
      <div>
        <h1 className="font-serif text-3xl tracking-tight">Knowledge Dashboard</h1>
        <p className="mt-1 font-mono text-xs uppercase tracking-widest text-[var(--alfred-text-tertiary)]">
          Last 30 days
        </p>
      </div>

      <LiveKnowledgeScore />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <RetentionCard />
        <CoverageCard />
        <ConnectionsCard />
      </div>

      <ActivityStrip />
    </div>
  );
}

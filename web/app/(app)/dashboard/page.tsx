import { KnowledgeScore } from "./_components/knowledge-score";
import { RetentionCard } from "./_components/retention-card";
import { CoverageCard } from "./_components/coverage-card";
import { ConnectionsCard } from "./_components/connections-card";
import { ActivityStrip } from "./_components/activity-strip";

export const metadata = { title: "Dashboard — Alfred" };

export default function DashboardPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6">
      <KnowledgeScore retention={0} coverage={0} connections={0} />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <RetentionCard />
        <CoverageCard />
        <ConnectionsCard />
      </div>

      <ActivityStrip />
    </div>
  );
}

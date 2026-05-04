import { Page } from "@/components/layout/page";
import { AgentsListClient } from "./_components/agents-list-client";

export const metadata = { title: "Research agents — Alfred" };

export default function ResearchAgentsPage() {
  return (
    <Page size="full" className="p-0">
      <AgentsListClient />
    </Page>
  );
}

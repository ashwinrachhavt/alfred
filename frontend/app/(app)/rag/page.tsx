import { MessageCircle } from "lucide-react";

import { Page } from "@/components/layout/page";
import { EmptyState } from "@/components/ui/empty-state";

export default function RagPage() {
  return (
    <Page>
      <EmptyState
        icon={MessageCircle}
        title="Knowledge Assistant (RAG)"
        description="Coming next: chat with citations, context viewer, and modes."
      />
    </Page>
  );
}

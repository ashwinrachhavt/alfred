import { FileText } from "lucide-react";

import { Page } from "@/components/layout/page";
import { EmptyState } from "@/components/ui/empty-state";

export default function DocumentsPage() {
  return (
    <Page>
      <EmptyState
        icon={FileText}
        title="Documents & Notes"
        description="Coming next: uploads, rich notes, tagging, and search."
      />
    </Page>
  );
}

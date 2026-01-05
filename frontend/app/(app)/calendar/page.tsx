import { Calendar } from "lucide-react";

import { Page } from "@/components/layout/page";
import { EmptyState } from "@/components/ui/empty-state";

export default function CalendarPage() {
  return (
    <Page>
      <EmptyState
        icon={Calendar}
        title="Calendar & Email"
        description="Coming next: OAuth connection cards, calendar views, and email threads."
      />
    </Page>
  );
}

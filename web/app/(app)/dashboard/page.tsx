import { DashboardClient } from "@/app/(app)/dashboard/_components/dashboard-client";
import { Page } from "@/components/layout/page";

export default function DashboardPage() {
  return (
    <Page size="wide">
      <DashboardClient />
    </Page>
  );
}

import { Page } from "@/components/layout/page";
import { NotionClient } from "@/app/(app)/notion/_components/notion-client";

export default function NotionPage() {
  return (
    <Page size="wide">
      <NotionClient />
    </Page>
  );
}

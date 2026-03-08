import { Page } from "@/components/layout/page";
import { DocumentsClient } from "@/app/(app)/documents/_components/documents-client";

export default function LibraryPage() {
  return (
    <Page size="wide">
      <DocumentsClient />
    </Page>
  );
}

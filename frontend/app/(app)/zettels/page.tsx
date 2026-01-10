import { ZettelsClient } from "@/app/(app)/zettels/_components/zettels-client";
import { Page } from "@/components/layout/page";

export default function ZettelsPage() {
  return (
    <Page size="wide">
      <ZettelsClient />
    </Page>
  );
}


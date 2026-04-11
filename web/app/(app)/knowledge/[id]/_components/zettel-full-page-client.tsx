"use client";

import { Page } from "@/components/layout/page";
import { ZettelFullView } from "@/app/(app)/knowledge/_components/zettel-full-view";

export function ZettelFullPageClient({ zettelId }: { zettelId: number }) {
  return (
    <Page size="comfortable" className="min-h-[calc(100dvh-3.5rem)]">
      <ZettelFullView zettelId={zettelId} />
    </Page>
  );
}

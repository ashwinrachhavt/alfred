import { Suspense } from "react";

import { ResearchClient } from "@/app/(app)/research/_components/research-client";
import { Page } from "@/components/layout/page";

export default function ResearchPage() {
  return (
    <Page size="full" className="p-0">
      <Suspense fallback={null}>
        <ResearchClient />
      </Suspense>
    </Page>
  );
}

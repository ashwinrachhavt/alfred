import { Page } from "@/components/layout/page";

import { ZettelCardClient } from "./_components/zettel-card-client";

export default function ZettelCardPage({ params }: { params: { cardId: string } }) {
  const cardId = Number(params.cardId);
  return (
    <Page size="comfortable">
      <ZettelCardClient cardId={cardId} />
    </Page>
  );
}


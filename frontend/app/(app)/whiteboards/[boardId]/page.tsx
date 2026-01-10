import { Page } from "@/components/layout/page";

import { WhiteboardClient } from "./_components/whiteboard-client";

export default function WhiteboardPage({ params }: { params: { boardId: string } }) {
  const boardId = Number(params.boardId);
  return (
    <Page size="comfortable">
      <WhiteboardClient boardId={boardId} />
    </Page>
  );
}


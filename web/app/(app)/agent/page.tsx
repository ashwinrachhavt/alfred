import { Page } from "@/components/layout/page";
import { AgentChatClient } from "./_components/agent-chat-client";

export const metadata = { title: "Alfred Agent" };

export default function AgentPage() {
  return (
    <Page size="full" className="p-0">
      <AgentChatClient />
    </Page>
  );
}

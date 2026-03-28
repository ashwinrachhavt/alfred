import { KnowledgeHub } from "./_components/knowledge-hub";

export const metadata = { title: "Knowledge — Alfred" };

export default function KnowledgePage() {
  return (
    <div className="h-[calc(100dvh-3.5rem)]">
      <KnowledgeHub />
    </div>
  );
}

import { Page } from "@/components/layout/page";
import { SessionEditorShell } from "@/app/(app)/think/[sessionId]/_components/session-editor-shell";

type SessionPageProps = {
 params: Promise<{ sessionId: string }>;
};

export default async function SessionPage({ params }: SessionPageProps) {
 const { sessionId } = await params;
 const id = Number(sessionId);

 return (
 <Page size="full" className="p-0">
 <SessionEditorShell sessionId={id} />
 </Page>
 );
}

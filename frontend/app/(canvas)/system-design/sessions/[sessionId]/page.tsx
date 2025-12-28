import { SystemDesignSessionClient } from "@/app/(canvas)/system-design/sessions/[sessionId]/_components/system-design-session-client";

export default async function SystemDesignSessionPage({
  params,
}: {
  params: { sessionId: string } | Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;

  return (
    <div className="h-dvh w-full">
      <SystemDesignSessionClient sessionId={sessionId} />
    </div>
  );
}

import { SharedSystemDesignSessionClient } from "@/app/(canvas)/system-design/share/[shareId]/shared-system-design-session-client";

export default async function SystemDesignSharePage({
  params,
}: {
  params: { shareId: string } | Promise<{ shareId: string }>;
}) {
  const { shareId } = await params;

  return (
    <div className="h-dvh w-full">
      <SharedSystemDesignSessionClient shareId={shareId} />
    </div>
  );
}

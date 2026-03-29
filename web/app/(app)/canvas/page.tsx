import { CanvasWorkbenchClient } from "./_components/canvas-workbench-client";

export const metadata = { title: "Canvas — Alfred" };

type CanvasPageProps = {
  searchParams?: Promise<{
    id?: string | string[];
  }>;
};

function first(value: string | string[] | undefined): string | undefined {
  if (!value) return undefined;
  return Array.isArray(value) ? value[0] : value;
}

export default async function CanvasPage({ searchParams }: CanvasPageProps) {
  const params = await searchParams;
  const rawId = first(params?.id);
  const initialCanvasId = rawId ? Number(rawId) : null;

  return (
    <div className="h-[calc(100dvh-3rem)]">
      <CanvasWorkbenchClient initialCanvasId={initialCanvasId} />
    </div>
  );
}

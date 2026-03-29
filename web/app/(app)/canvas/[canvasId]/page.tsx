import { redirect } from "next/navigation";

type CanvasDetailPageProps = {
 params: Promise<{ canvasId: string }>;
};

/**
 * Redirect /canvas/[canvasId] to /canvas?id=[canvasId] for backwards compatibility.
 * The main canvas page now handles everything via query params.
 */
export default async function CanvasDetailPage({ params }: CanvasDetailPageProps) {
 const { canvasId } = await params;
 redirect(`/canvas?id=${encodeURIComponent(canvasId)}`);
}

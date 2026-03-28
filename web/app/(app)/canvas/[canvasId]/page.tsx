import { CanvasWorkspace } from "../_components/canvas-workspace";

export const metadata = { title: "Canvas — Alfred" };

export default function CanvasDetailPage() {
  return (
    <div className="h-[calc(100dvh-3rem)]">
      <CanvasWorkspace />
    </div>
  );
}

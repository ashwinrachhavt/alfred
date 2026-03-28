import { ExcalidrawWhiteboard } from "./_components/excalidraw-whiteboard";

export const metadata = { title: "Canvas — Alfred" };

export default function CanvasPage() {
  return (
    <div className="h-[calc(100dvh-3rem)]">
      <ExcalidrawWhiteboard />
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useCanvasStore } from "@/lib/stores/canvas-store";

type Whiteboard = { id: number; title: string };

export function CanvasSelector() {
  const { activeCanvasId, setActiveCanvas } = useCanvasStore();

  const { data: boards } = useQuery({
    queryKey: ["whiteboards"],
    queryFn: () => apiFetch<Whiteboard[]>(apiRoutes.whiteboards.list),
    staleTime: 30_000,
  });

  if (!boards || boards.length === 0) return null;

  return (
    <Select value={activeCanvasId ?? undefined} onValueChange={setActiveCanvas}>
      <SelectTrigger className="w-48 h-8 text-xs">
        <SelectValue placeholder="Select canvas" />
      </SelectTrigger>
      <SelectContent>
        {boards.map((b) => (
          <SelectItem key={b.id} value={String(b.id)}>
            {b.title}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

"use client";

import { X } from "lucide-react";

import {
  ExcalidrawCanvas,
  type ExcalidrawCanvasHandle,
  type ExcalidrawCanvasSelection,
} from "@/components/system-design/excalidraw-canvas";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import type { ExcalidrawData } from "@/lib/api/types/system-design";

export interface SessionCanvasProps {
  canvasRef: React.RefObject<ExcalidrawCanvasHandle | null>;
  initialDiagram: ExcalidrawData;
  isResizing: boolean;

  isPropertiesOpen: boolean;
  propertiesTarget: ExcalidrawCanvasSelection | null;
  propertiesName: string;

  onDiagramChange: (diagram: ExcalidrawData) => void;
  onSelectionChange: (ids: string[]) => void;
  onSelectionDetailsChange: (selection: ExcalidrawCanvasSelection | null) => void;
  onCanvasDoubleClick: () => void;

  onPropertiesNameChange: (name: string) => void;
  onPropertiesClose: () => void;
  onApplyName: () => void;
}

export function SessionCanvas({
  canvasRef,
  initialDiagram,
  isResizing,
  isPropertiesOpen,
  propertiesTarget,
  propertiesName,
  onDiagramChange,
  onSelectionChange,
  onSelectionDetailsChange,
  onCanvasDoubleClick,
  onPropertiesNameChange,
  onPropertiesClose,
  onApplyName,
}: SessionCanvasProps) {
  return (
    <div className="bg-background relative flex min-h-0 flex-col overflow-hidden rounded-xl border">
      {/* Overlay during resize to prevent event trapping */}
      {isResizing && <div className="absolute inset-0 z-50 bg-transparent" />}

      <div
        className="relative min-h-0 flex-1"
        onDoubleClick={onCanvasDoubleClick}
      >
        <ExcalidrawCanvas
          ref={canvasRef}
          initialDiagram={initialDiagram}
          onDiagramChange={onDiagramChange}
          onSelectionChange={onSelectionChange}
          onSelectionDetailsChange={onSelectionDetailsChange}
          framed={false}
          viewportScale={1}
        />

        {isPropertiesOpen && propertiesTarget ? (
          <Card
            className="bg-background/95 absolute top-3 right-3 z-20 w-80 border shadow-lg backdrop-blur"
            onDoubleClick={(event) => event.stopPropagation()}
          >
            <CardHeader className="flex flex-row items-center justify-between space-y-0 px-4 py-3">
              <CardTitle className="text-sm">Properties</CardTitle>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={onPropertiesClose}
              >
                <X className="size-4" />
              </Button>
            </CardHeader>
            <CardContent className="space-y-4 px-4 pb-4">
              <div className="flex flex-wrap gap-2">
                {propertiesTarget.category ? (
                  <Badge variant="secondary">
                    {propertiesTarget.category.replaceAll("_", " ")}
                  </Badge>
                ) : (
                  <Badge variant="secondary">component</Badge>
                )}
                <Badge variant="outline">id: {propertiesTarget.elementId}</Badge>
              </div>

              <div className="space-y-2">
                <Label htmlFor="sd-component-name">Name</Label>
                <Input
                  id="sd-component-name"
                  value={propertiesName}
                  onChange={(e) => onPropertiesNameChange(e.target.value)}
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key !== "Enter") return;
                    onApplyName();
                  }}
                />
              </div>

              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={onPropertiesClose}
                >
                  Close
                </Button>
                <Button
                  size="sm"
                  disabled={!propertiesName.trim()}
                  onClick={onApplyName}
                >
                  Apply
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

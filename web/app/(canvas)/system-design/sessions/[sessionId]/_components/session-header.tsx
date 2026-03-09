"use client";

import Link from "next/link";
import {
  Download,
  Link2,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Shapes,
  WandSparkles,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { diagramToMermaid, diagramToPlantUml } from "@/lib/system-design/code-export";

import type { ExcalidrawCanvasHandle } from "@/components/system-design/excalidraw-canvas";
import { SystemDesignComponentPalette } from "@/components/system-design/system-design-component-palette";
import { SystemDesignShareDialog } from "@/components/system-design/system-design-share-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

import type { SystemDesignSession } from "@/lib/api/types/system-design";

export interface SessionHeaderProps {
  session: SystemDesignSession;
  onSessionUpdated: (session: SystemDesignSession) => void;

  showDiagram: boolean;
  showEditor: boolean;
  showCoach: boolean;
  onToggleDiagram: () => void;
  onToggleEditor: () => void;
  onToggleCoach: () => void;

  isComponentPaletteOpen: boolean;
  onComponentPaletteOpenChange: (open: boolean) => void;

  isExportOpen: boolean;
  onExportOpenChange: (open: boolean) => void;

  isConnectMode: boolean;
  selectedElementIds: string[];
  onConnectClick: () => void;

  canvasRef: React.RefObject<ExcalidrawCanvasHandle | null>;

  exportBackground: boolean;
  onExportBackgroundChange: (checked: boolean) => void;
  pngMaxWidthOrHeight: number;
  onPngMaxWidthOrHeightChange: (value: number) => void;

  onOpenAiDialog: () => void;

  // Export helpers
  downloadBlob: (blob: Blob, filename: string) => void;
  downloadTextFile: (text: string, filename: string, mimeType: string) => void;
  copyToClipboard: (text: string) => Promise<void>;
  toExportBasename: (title: string | null | undefined, id: string) => string;
}

export function SessionHeader({
  session,
  onSessionUpdated,
  showDiagram,
  showEditor,
  showCoach,
  onToggleDiagram,
  onToggleEditor,
  onToggleCoach,
  isComponentPaletteOpen,
  onComponentPaletteOpenChange,
  isExportOpen,
  onExportOpenChange,
  isConnectMode,
  selectedElementIds,
  onConnectClick,
  canvasRef,
  exportBackground,
  onExportBackgroundChange,
  pngMaxWidthOrHeight,
  onPngMaxWidthOrHeightChange,
  onOpenAiDialog,
  downloadBlob,
  downloadTextFile,
  copyToClipboard,
  toExportBasename,
}: SessionHeaderProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="space-y-1">
        <h1 className="text-xl font-semibold tracking-tight">
          {session.title ?? "System Design Session"}
        </h1>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="default"
          size="sm"
          className="gap-2"
          onClick={onOpenAiDialog}
          disabled={!showDiagram}
          title={
            !showDiagram ? "Show Diagram to generate into the canvas." : "Generate a new diagram"
          }
        >
          <WandSparkles className="size-4" />
          Generate
        </Button>

        <Sheet open={isComponentPaletteOpen} onOpenChange={onComponentPaletteOpenChange}>
          <SheetTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              disabled={!showDiagram}
              title={!showDiagram ? "Show Diagram to insert components." : "Open component library"}
            >
              <Shapes className="size-4" />
              Components
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[420px] sm:max-w-md">
            <SheetHeader>
              <SheetTitle>Component library</SheetTitle>
              <SheetDescription>
                Click a component to drop it onto the canvas.
              </SheetDescription>
            </SheetHeader>
            <div className="min-h-0 flex-1 overflow-hidden">
              <SystemDesignComponentPalette
                showHeader={false}
                onInsert={(component) => {
                  canvasRef.current?.insertComponent(component);
                }}
              />
            </div>
          </SheetContent>
        </Sheet>

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={isConnectMode ? "secondary" : "outline"}
              size="sm"
              className="gap-2"
              disabled={!showDiagram || (!isConnectMode && selectedElementIds.length !== 1)}
              onClick={onConnectClick}
            >
              <Link2 className="size-4" />
              {isConnectMode ? "Cancel connect" : "Connect"}
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {isConnectMode
              ? "Select a target component on the canvas."
              : selectedElementIds.length === 1
                ? "Connect selected component to another."
                : "Select exactly one component to start a connection."}
          </TooltipContent>
        </Tooltip>

        <Sheet open={isExportOpen} onOpenChange={onExportOpenChange}>
          <SheetTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              disabled={!showDiagram}
              title={!showDiagram ? "Show Diagram to export." : "Export diagram"}
            >
              <Download className="size-4" />
              Export
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-[420px] sm:max-w-md">
            <SheetHeader>
              <SheetTitle>Export</SheetTitle>
              <SheetDescription>Download images or copy diagram code.</SheetDescription>
            </SheetHeader>

            <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
              <div className="space-y-3">
                <div className="space-y-1">
                  <h3 className="text-sm font-medium">PNG</h3>
                  <p className="text-muted-foreground text-xs">
                    Exports the current canvas view as a PNG.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="sd-export-png-max">Max size</Label>
                    <select
                      id="sd-export-png-max"
                      className="bg-background h-9 rounded-md border px-3 text-sm"
                      value={pngMaxWidthOrHeight}
                      onChange={(e) => onPngMaxWidthOrHeightChange(Number(e.target.value))}
                    >
                      <option value={0}>Default</option>
                      <option value={1920}>1080p (max 1920px)</option>
                      <option value={3840}>4K (max 3840px)</option>
                    </select>
                  </div>

                  <div className="space-y-1">
                    <Label htmlFor="sd-export-background">Background</Label>
                    <div className="flex h-9 items-center">
                      <Switch
                        id="sd-export-background"
                        checked={exportBackground}
                        onCheckedChange={onExportBackgroundChange}
                      />
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    onClick={async () => {
                      const blob = await canvasRef.current?.exportPng({
                        maxWidthOrHeight: pngMaxWidthOrHeight || undefined,
                        background: exportBackground,
                      });
                      if (!blob) return;
                      downloadBlob(blob, `${toExportBasename(session.title, session.id)}.png`);
                    }}
                  >
                    Download PNG
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      const svg = await canvasRef.current?.exportSvg({ embedScene: true });
                      if (!svg) return;
                      downloadTextFile(
                        svg,
                        `${toExportBasename(session.title, session.id)}.svg`,
                        "image/svg+xml",
                      );
                    }}
                  >
                    Download SVG
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={async () => {
                      const svg = await canvasRef.current?.exportSvg({ embedScene: false });
                      if (!svg) return;
                      const win = window.open("", "_blank", "noopener,noreferrer");
                      if (!win) return;
                      win.document.open();
                      win.document.write(`<!doctype html><html><head><title>Export</title></head><body style="margin:0">${svg}</body></html>`);
                      win.document.close();
                      win.focus();
                      win.print();
                    }}
                  >
                    Print (PDF)
                  </Button>
                </div>
              </div>

              <Separator />

              <div className="space-y-3">
                <div className="space-y-1">
                  <h3 className="text-sm font-medium">Code</h3>
                  <p className="text-muted-foreground text-xs">
                    Generates a basic diagram graph from bound arrows.
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const diagram = canvasRef.current?.getDiagram() ?? session.diagram;
                      void copyToClipboard(diagramToMermaid(diagram));
                    }}
                  >
                    Copy Mermaid
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const diagram = canvasRef.current?.getDiagram() ?? session.diagram;
                      void copyToClipboard(diagramToPlantUml(diagram));
                    }}
                  >
                    Copy PlantUML
                  </Button>
                </div>
              </div>

              <Separator />

              <div className="space-y-3">
                <div className="space-y-1">
                  <h3 className="text-sm font-medium">Raw</h3>
                  <p className="text-muted-foreground text-xs">
                    Downloads the persisted Excalidraw JSON for version control.
                  </p>
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const diagram = canvasRef.current?.getDiagram() ?? session.diagram;
                    downloadTextFile(
                      JSON.stringify(diagram, null, 2),
                      `${toExportBasename(session.title, session.id)}.excalidraw.json`,
                      "application/json",
                    );
                  }}
                >
                  Download JSON
                </Button>
              </div>
            </div>
          </SheetContent>
        </Sheet>

        <div className="bg-background/70 flex items-center rounded-xl border p-1 shadow-sm backdrop-blur-sm">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                className={cn(
                  "rounded-lg",
                  showDiagram ? "bg-accent text-accent-foreground hover:bg-accent/80" : "",
                )}
                onClick={onToggleDiagram}
              >
                {showDiagram ? (
                  <PanelLeftClose className="size-4" />
                ) : (
                  <PanelLeftOpen className="size-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{showDiagram ? "Hide diagram" : "Show diagram"}</TooltipContent>
          </Tooltip>

          <div className="bg-border mx-1 h-6 w-px" />

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                className={cn(
                  "rounded-lg",
                  showEditor ? "bg-accent text-accent-foreground hover:bg-accent/80" : "",
                )}
                onClick={onToggleEditor}
              >
                {showEditor ? (
                  <PanelRightClose className="size-4" />
                ) : (
                  <PanelRightOpen className="size-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{showEditor ? "Hide editor" : "Show editor"}</TooltipContent>
          </Tooltip>

          <div className="bg-border mx-1 h-6 w-px" />

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon-sm"
                className={cn(
                  "rounded-lg",
                  showCoach ? "bg-accent text-accent-foreground hover:bg-accent/80" : "",
                )}
                onClick={onToggleCoach}
              >
                {showCoach ? (
                  <PanelRightClose className="size-4" />
                ) : (
                  <PanelRightOpen className="size-4" />
                )}
              </Button>
            </TooltipTrigger>
            <TooltipContent>{showCoach ? "Hide coach" : "Show coach"}</TooltipContent>
          </Tooltip>
        </div>

        <SystemDesignShareDialog session={session} onSessionUpdated={onSessionUpdated} />
        <Button asChild variant="ghost" size="sm">
          <Link href="/system-design">Exit</Link>
        </Button>
      </div>
    </div>
  );
}

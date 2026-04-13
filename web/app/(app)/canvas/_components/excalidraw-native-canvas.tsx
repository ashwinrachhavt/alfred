"use client";

import { Excalidraw, TTDDialog, TTDDialogTrigger } from "@excalidraw/excalidraw";
import type React from "react";

type NativeTextSubmitResult = {
  generatedResponse?: string;
  error?: Error | null;
  rateLimit?: number | null;
  rateLimitRemaining?: number | null;
};

type ExcalidrawNativeCanvasProps = React.ComponentProps<typeof Excalidraw> & {
  onTextSubmit: (value: string) => Promise<NativeTextSubmitResult>;
};

export function ExcalidrawNativeCanvas({
  onTextSubmit,
  children,
  ...props
}: ExcalidrawNativeCanvasProps) {
  return (
    <Excalidraw {...props}>
      {children}
      <TTDDialogTrigger />
      <TTDDialog onTextSubmit={onTextSubmit} />
    </Excalidraw>
  );
}

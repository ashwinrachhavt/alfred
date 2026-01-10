"use client";

import type { ExcalidrawData } from "@/lib/api/types/system-design";

export type DiagramPngExportOptions = {
  transparent?: boolean;
  maxWidth?: number;
  maxHeight?: number;
  embedScene?: boolean;
};

export type DiagramSvgExportOptions = {
  transparent?: boolean;
  embedScene?: boolean;
};

function clampNumber(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function blobToArrayBuffer(blob: Blob): Promise<ArrayBuffer> {
  return await blob.arrayBuffer();
}

function guessSafeFilename(base: string, ext: string): string {
  const cleaned = base
    .trim()
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, " ")
    .slice(0, 80);
  return `${cleaned || "diagram"}.${ext}`;
}

export async function exportDiagramToPng(
  diagram: ExcalidrawData,
  { filenameBase, options }: { filenameBase: string; options: DiagramPngExportOptions },
): Promise<void> {
  const { exportToBlob } = await import("@excalidraw/excalidraw");

  const files = Object.keys(diagram.files ?? {}).length ? (diagram.files as never) : null;
  const blob = await exportToBlob({
    elements: diagram.elements as never,
    appState: {
      ...diagram.appState,
      exportBackground: !options.transparent,
      exportEmbedScene: options.embedScene ?? true,
    } as never,
    files,
    mimeType: "image/png",
    exportPadding: 16,
  });

  const filename = guessSafeFilename(filenameBase, "png");

  // If the diagram is extremely large, downscale to stay within requested bounds.
  const maxWidth = options.maxWidth ?? 3840;
  const maxHeight = options.maxHeight ?? 2160;
  const img = document.createElement("img");
  img.decoding = "async";

  const url = URL.createObjectURL(blob);
  try {
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error("Failed to load image for export."));
      img.src = url;
    });

    const needsResize = img.width > maxWidth || img.height > maxHeight;
    if (!needsResize) {
      downloadBlob(blob, filename);
      return;
    }

    const scale = Math.min(maxWidth / img.width, maxHeight / img.height);
    const targetWidth = clampNumber(Math.round(img.width * scale), 1, maxWidth);
    const targetHeight = clampNumber(Math.round(img.height * scale), 1, maxHeight);

    const canvas = document.createElement("canvas");
    canvas.width = targetWidth;
    canvas.height = targetHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Canvas 2D context unavailable.");
    ctx.drawImage(img, 0, 0, targetWidth, targetHeight);

    const resized = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (out) => (out ? resolve(out) : reject(new Error("Failed to create PNG."))),
        "image/png",
      );
    });
    downloadBlob(resized, filename);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function exportDiagramToSvg(
  diagram: ExcalidrawData,
  { filenameBase, options }: { filenameBase: string; options: DiagramSvgExportOptions },
): Promise<void> {
  const { exportToSvg } = await import("@excalidraw/excalidraw");

  const files = Object.keys(diagram.files ?? {}).length ? (diagram.files as never) : null;
  const svgEl = await Promise.resolve(
    exportToSvg({
      elements: diagram.elements as never,
      appState: {
        ...diagram.appState,
        exportBackground: !options.transparent,
        exportEmbedScene: options.embedScene ?? true,
      } as never,
      files,
      exportPadding: 16,
    }),
  );

  const markup = svgEl.outerHTML;
  const blob = new Blob([markup], { type: "image/svg+xml;charset=utf-8" });
  downloadBlob(blob, guessSafeFilename(filenameBase, "svg"));
}

export async function exportDiagramToPdfViaPng(
  diagram: ExcalidrawData,
  { filenameBase, options }: { filenameBase: string; options: DiagramPngExportOptions },
): Promise<void> {
  const { exportToBlob } = await import("@excalidraw/excalidraw");
  const { PDFDocument } = await import("pdf-lib");

  const files = Object.keys(diagram.files ?? {}).length ? (diagram.files as never) : null;
  const png = await exportToBlob({
    elements: diagram.elements as never,
    appState: {
      ...diagram.appState,
      exportBackground: !options.transparent,
      exportEmbedScene: options.embedScene ?? true,
    } as never,
    files,
    mimeType: "image/png",
    exportPadding: 16,
  });

  const bytes = await blobToArrayBuffer(png);
  const doc = await PDFDocument.create();
  const image = await doc.embedPng(bytes);
  const page = doc.addPage([image.width, image.height]);
  page.drawImage(image, { x: 0, y: 0, width: image.width, height: image.height });
  const pdfBytes = await doc.save();
  const pdfBytesCopy = new Uint8Array(pdfBytes);
  downloadBlob(
    new Blob([pdfBytesCopy], { type: "application/pdf" }),
    guessSafeFilename(filenameBase, "pdf"),
  );
}

"use client";

import { useMemo, useState } from "react";
import { Download, FileText, Image as ImageIcon, Layers, Save } from "lucide-react";
import { toast } from "sonner";

import {
 createSystemDesignTemplate,
 exportSystemDesignMermaid,
 exportSystemDesignPlantUml,
} from "@/lib/api/system-design";
import type { ExcalidrawData, SystemDesignSession } from "@/lib/api/types/system-design";

import {
 downloadBlob,
 exportDiagramToPdfViaPng,
 exportDiagramToPng,
 exportDiagramToSvg,
} from "@/lib/system-design/export";

import { Button } from "@/components/ui/button";
import {
 Dialog,
 DialogContent,
 DialogDescription,
 DialogFooter,
 DialogHeader,
 DialogTitle,
} from "@/components/ui/dialog";
import {
 DropdownMenu,
 DropdownMenuContent,
 DropdownMenuItem,
 DropdownMenuLabel,
 DropdownMenuSeparator,
 DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

async function copyToClipboard(text: string, label: string) {
 try {
 await navigator.clipboard.writeText(text);
 toast.success(`${label} copied`);
 } catch {
 toast.error("Copy failed");
 }
}

function downloadText(text: string, filename: string) {
 downloadBlob(new Blob([text], { type: "text/plain;charset=utf-8" }), filename);
}

export function SystemDesignExportMenu({
 session,
 getDiagram,
 beforeExport,
}: {
 session: SystemDesignSession;
 getDiagram: () => ExcalidrawData | null;
 beforeExport?: () => Promise<void>;
}) {
 const [isSavingTemplate, setIsSavingTemplate] = useState(false);
 const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);
 const [templateName, setTemplateName] = useState("");
 const [templateDescription, setTemplateDescription] = useState("");

 const filenameBase = useMemo(
 () => (session.title?.trim() ? session.title.trim() :`system-design-${session.id}`),
 [session.id, session.title],
 );

 async function withDiagram<T>(fn: (diagram: ExcalidrawData) => Promise<T>): Promise<T> {
 if (beforeExport) {
 await beforeExport();
 }
 const diagram = getDiagram();
 if (!diagram) throw new Error("Diagram not ready yet.");
 return await fn(diagram);
 }

 async function onExportPng(transparent: boolean) {
 try {
 await withDiagram((diagram) =>
 exportDiagramToPng(diagram, {
 filenameBase,
 options: { transparent, maxWidth: 3840, maxHeight: 2160, embedScene: true },
 }),
 );
 toast.success("PNG exported");
 } catch (err) {
 toast.error(err instanceof Error ? err.message : "Failed to export PNG.");
 }
 }

 async function onExportSvg(transparent: boolean) {
 try {
 await withDiagram((diagram) =>
 exportDiagramToSvg(diagram, { filenameBase, options: { transparent, embedScene: true } }),
 );
 toast.success("SVG exported");
 } catch (err) {
 toast.error(err instanceof Error ? err.message : "Failed to export SVG.");
 }
 }

 async function onExportPdf() {
 try {
 await withDiagram((diagram) =>
 exportDiagramToPdfViaPng(diagram, {
 filenameBase,
 options: { transparent: false, maxWidth: 3840, maxHeight: 2160, embedScene: true },
 }),
 );
 toast.success("PDF exported");
 } catch (err) {
 toast.error(err instanceof Error ? err.message : "Failed to export PDF.");
 }
 }

 async function onExportMermaid(copyOnly: boolean) {
 try {
 if (beforeExport) await beforeExport();
 const mermaid = await exportSystemDesignMermaid(session.id);
 if (copyOnly) {
 await copyToClipboard(mermaid, "Mermaid");
 } else {
 downloadText(mermaid,`${filenameBase}.mmd`);
 toast.success("Mermaid downloaded");
 }
 } catch (err) {
 toast.error(err instanceof Error ? err.message : "Failed to export Mermaid.");
 }
 }

 async function onExportPlantUml(copyOnly: boolean) {
 try {
 if (beforeExport) await beforeExport();
 const plantuml = await exportSystemDesignPlantUml(session.id);
 if (copyOnly) {
 await copyToClipboard(plantuml, "PlantUML");
 } else {
 downloadText(plantuml,`${filenameBase}.puml`);
 toast.success("PlantUML downloaded");
 }
 } catch (err) {
 toast.error(err instanceof Error ? err.message : "Failed to export PlantUML.");
 }
 }

 async function onSaveTemplate() {
 const diagram = getDiagram();
 if (!diagram) {
 toast.error("Diagram not ready yet.");
 return;
 }

 setIsSavingTemplate(true);
 try {
 await createSystemDesignTemplate({
 name: templateName.trim(),
 description: templateDescription.trim(),
 components: [],
 diagram,
 });
 toast.success("Template saved");
 setTemplateName("");
 setTemplateDescription("");
 setSaveTemplateOpen(false);
 } catch (err) {
 toast.error(err instanceof Error ? err.message : "Failed to save template.");
 } finally {
 setIsSavingTemplate(false);
 }
 }

 return (
 <>
 <DropdownMenu>
 <DropdownMenuTrigger asChild>
 <Button variant="outline" size="sm" className="gap-2">
 <Download className="size-4" />
 Export
 </Button>
 </DropdownMenuTrigger>
 <DropdownMenuContent align="end" className="w-56">
 <DropdownMenuLabel>Image</DropdownMenuLabel>
 <DropdownMenuItem onClick={() => void onExportPng(false)}>
 <ImageIcon className="size-4" />
 PNG (4K)
 </DropdownMenuItem>
 <DropdownMenuItem onClick={() => void onExportPng(true)}>
 <ImageIcon className="size-4" />
 PNG (transparent)
 </DropdownMenuItem>
 <DropdownMenuItem onClick={() => void onExportSvg(false)}>
 <Layers className="size-4" />
 SVG (editable)
 </DropdownMenuItem>
 <DropdownMenuItem onClick={() => void onExportSvg(true)}>
 <Layers className="size-4" />
 SVG (transparent)
 </DropdownMenuItem>
 <DropdownMenuItem onClick={() => void onExportPdf()}>
 <FileText className="size-4" />
 PDF
 </DropdownMenuItem>

 <DropdownMenuSeparator />
 <DropdownMenuLabel>Code</DropdownMenuLabel>
 <DropdownMenuItem onClick={() => void onExportMermaid(true)}>
 Copy Mermaid
 </DropdownMenuItem>
 <DropdownMenuItem onClick={() => void onExportMermaid(false)}>
 Download Mermaid
 </DropdownMenuItem>
 <DropdownMenuItem onClick={() => void onExportPlantUml(true)}>
 Copy PlantUML
 </DropdownMenuItem>
 <DropdownMenuItem onClick={() => void onExportPlantUml(false)}>
 Download PlantUML
 </DropdownMenuItem>

 <DropdownMenuSeparator />
 <DropdownMenuItem onClick={() => setSaveTemplateOpen(true)}>
 <Save className="size-4" />
 Save as template…
 </DropdownMenuItem>
 </DropdownMenuContent>
 </DropdownMenu>

 <Dialog open={saveTemplateOpen} onOpenChange={setSaveTemplateOpen}>
 <DialogContent>
 <DialogHeader>
 <DialogTitle>Save as template</DialogTitle>
 <DialogDescription>
 Save the current diagram as a reusable template for new sessions.
 </DialogDescription>
 </DialogHeader>

 <div className="space-y-4">
 <div className="space-y-2">
 <Label htmlFor="sdTemplateName">Name</Label>
 <Input
 id="sdTemplateName"
 value={templateName}
 onChange={(e) => setTemplateName(e.target.value)}
 placeholder="e.g. URL shortener (my variant)"
 />
 </div>
 <div className="space-y-2">
 <Label htmlFor="sdTemplateDesc">Description</Label>
 <Textarea
 id="sdTemplateDesc"
 value={templateDescription}
 onChange={(e) => setTemplateDescription(e.target.value)}
 rows={4}
 className="resize-none"
 placeholder="Short description to help you pick it later."
 />
 </div>
 </div>

 <DialogFooter>
 <Button type="button" variant="outline" onClick={() => setSaveTemplateOpen(false)}>
 Cancel
 </Button>
 <Button
 type="button"
 onClick={() => void onSaveTemplate()}
 disabled={isSavingTemplate || !templateName.trim()}
 >
 {isSavingTemplate ? "Saving…" : "Save template"}
 </Button>
 </DialogFooter>
 </DialogContent>
 </Dialog>
 </>
 );
}

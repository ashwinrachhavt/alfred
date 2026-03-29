"use client";

import { EditorContent, type Editor, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import { Markdown } from "@tiptap/markdown";
import Typography from "@tiptap/extension-typography";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { cn } from "@/lib/utils";
import { useUpdateDocumentText } from "@/features/documents/mutations";

type TiptapMarkdownStorage = {
 markdown?: {
 getMarkdown?: () => string;
 };
};

function readEditorMarkdown(editor: Editor): string {
 const storage = editor.storage as unknown as TiptapMarkdownStorage;
 return storage.markdown?.getMarkdown?.() ?? "";
}

export type DocumentEditorProps = {
 docId: string;
 initialMarkdown: string;
 className?: string;
};

export function DocumentEditor({ docId, initialMarkdown, className }: DocumentEditorProps) {
 const updateMutation = useUpdateDocumentText(docId);

 const lastSavedMarkdownRef = useRef(initialMarkdown);
 const queuedSaveRef = useRef(false);
 const debounceTimerRef = useRef<number | null>(null);
 const [isFocused, setIsFocused] = useState(false);

 const draftRef = useRef<{ markdown: string; cleanedText: string; tiptapJson: unknown }>({
 markdown: initialMarkdown,
 cleanedText: "",
 tiptapJson: null,
 });

 const extensions = useMemo(
 () => [
 StarterKit.configure({
 heading: {
 levels: [1, 2, 3],
 },
 }),
 Markdown,
 Typography,
 Placeholder.configure({
 placeholder: "Write something…",
 emptyEditorClass: "is-editor-empty",
 }),
 ],
 [],
 );

 const saveNow = useCallback(async () => {
 const { markdown, cleanedText, tiptapJson } = draftRef.current;
 if (markdown === lastSavedMarkdownRef.current) return;

 if (updateMutation.isPending) {
 queuedSaveRef.current = true;
 return;
 }

 try {
 const updated = await updateMutation.mutateAsync({
 raw_markdown: markdown,
 cleaned_text: cleanedText,
 tiptap_json: (tiptapJson as Record<string, unknown> | null) ?? null,
 });
 lastSavedMarkdownRef.current = (
 updated.raw_markdown ??
 updated.cleaned_text ??
 ""
 ).toString();
 } catch (err) {
 toast.error(err instanceof Error ? err.message : "Failed to save document.");
 } finally {
 if (queuedSaveRef.current) {
 queuedSaveRef.current = false;
 void saveNow();
 }
 }
 }, [updateMutation]);

 const editor = useEditor({
 extensions,
 content: initialMarkdown,
 immediatelyRender: false,
 editorProps: {
 attributes: {
 class: cn(
 "prose dark:prose-invert max-w-none focus:outline-none min-h-[220px] px-4 py-4",
 "prose-headings:font-semibold prose-h1:text-2xl prose-h2:text-xl prose-h3:text-lg",
 "prose-pre:bg-muted prose-pre:text-foreground",
 "prose-blockquote:border-l-primary prose-blockquote:bg-muted/30 prose-blockquote:py-1 prose-blockquote:px-3 prose-blockquote:not-italic",
 ),
 },
 },
 onUpdate: ({ editor }) => {
 const markdown = readEditorMarkdown(editor);
 draftRef.current = {
 markdown,
 cleanedText: editor.getText(),
 tiptapJson: editor.getJSON(),
 };

 if (debounceTimerRef.current) {
 window.clearTimeout(debounceTimerRef.current);
 }
 debounceTimerRef.current = window.setTimeout(() => {
 void saveNow();
 }, 650);
 },
 onFocus: () => setIsFocused(true),
 onBlur: () => {
 setIsFocused(false);
 void saveNow();
 },
 });

 useEffect(() => {
 if (!editor) return;
 lastSavedMarkdownRef.current = readEditorMarkdown(editor);
 draftRef.current.cleanedText = editor.getText();
 draftRef.current.tiptapJson = editor.getJSON();
 }, [editor]);

 useEffect(() => {
 if (!editor) return;
 if (isFocused) return;

 const current = readEditorMarkdown(editor);
 if (initialMarkdown !== current) {
 editor.commands.setContent(initialMarkdown);
 lastSavedMarkdownRef.current = initialMarkdown;
 }
 }, [editor, initialMarkdown, isFocused]);

 useEffect(() => {
 return () => {
 if (debounceTimerRef.current) {
 window.clearTimeout(debounceTimerRef.current);
 }
 };
 }, []);

 return (
 <div className={cn("space-y-2", className)}>
 <div className="flex items-center justify-between">
 <p className="text-muted-foreground text-xs">
 {updateMutation.isPending ? "Saving…" : " "}
 </p>
 </div>

 <div className="bg-background rounded-2xl border">
 <EditorContent editor={editor} />
 </div>
 </div>
 );
}
